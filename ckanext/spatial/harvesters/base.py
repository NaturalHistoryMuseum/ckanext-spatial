#!/usr/bin/env python
# encoding: utf-8

import cgitb
import hashlib
import json
import logging
import mimetypes
import sys
import urllib2
import uuid
from datetime import datetime
from string import Template
from urlparse import urlparse

import dateutil
import re
import requests
import warnings
from ckanext.harvest.harvesters.base import HarvesterBase
from ckanext.harvest.model import HarvestObject
from ckanext.spatial.interfaces import ISpatialHarvester
from ckanext.spatial.model import ISODocument
from ckanext.spatial.validation import Validators, all_validators
from lxml import etree
from owslib import wms

from ckan import logic, model
from ckan.lib.search.index import PackageSearchIndex
from ckan.plugins import PluginImplementations, toolkit

log = logging.getLogger(__name__)

DEFAULT_VALIDATOR_PROFILES = [u'iso19139']


def text_traceback():
    ''' '''
    with warnings.catch_warnings():
        warnings.simplefilter(u'ignore')
        res = u'the original traceback:'.join(
            cgitb.text(sys.exc_info()).split(u'the original traceback:')[1:]
            ).strip()
    return res


def guess_standard(content):
    '''

    :param content: 

    '''
    lowered = content.lower()
    if u'</gmd:MD_Metadata>'.lower() in lowered:
        return u'iso'
    if u'</gmi:MI_Metadata>'.lower() in lowered:
        return u'iso'
    if u'</metadata>'.lower() in lowered:
        return u'fgdc'
    return u'unknown'


def guess_resource_format(url, use_mimetypes=True):
    '''Given a URL try to guess the best format to assign to the resource
    
    The function looks for common patterns in popular geospatial services and
    file extensions, so it may not be 100% accurate. It just looks at the
    provided URL, it does not attempt to perform any remote check.
    
    if 'use_mimetypes' is True (default value), the mimetypes module will be
    used if no match was found before.
    
    Returns None if no format could be guessed.

    :param url: 
    :param use_mimetypes:  (Default value = True)

    '''
    url = url.lower().strip()

    resource_types = {
        # OGC
        u'wms': (u'service=wms', u'geoserver/wms', u'mapserver/wmsserver',
                 u'com.esri.wms.Esrimap', u'service/wms'),
        u'wfs': (u'service=wfs', u'geoserver/wfs', u'mapserver/wfsserver',
                 u'com.esri.wfs.Esrimap'),
        u'wcs': (u'service=wcs', u'geoserver/wcs', u'imageserver/wcsserver',
                 u'mapserver/wcsserver'),
        u'sos': (u'service=sos',),
        u'csw': (u'service=csw',),
        # ESRI
        u'kml': (u'mapserver/generatekml',),
        u'arcims': (u'com.esri.esrimap.esrimap',),
        u'arcgis_rest': (u'arcgis/rest/services',),
        }

    for resource_type, parts in resource_types.iteritems():
        if any(part in url for part in parts):
            return resource_type

    file_types = {
        u'kml': (u'kml',),
        u'kmz': (u'kmz',),
        u'gml': (u'gml',),
        }

    for file_type, extensions in file_types.iteritems():
        if any(url.endswith(extension) for extension in extensions):
            return file_type

    resource_format, encoding = mimetypes.guess_type(url)
    if resource_format:
        return resource_format

    return None


class SpatialHarvester(HarvesterBase):
    ''' '''

    _user_name = None

    _site_user = None

    source_config = {}

    force_import = False

    extent_template = Template(u'''
    {"type": "Polygon", "coordinates": [[[$xmin, $ymin], [$xmax, $ymin], [$xmax, 
    $ymax], [$xmin, $ymax], [$xmin, $ymin]]]}
    ''')

    ## IHarvester

    def validate_config(self, source_config):
        '''

        :param source_config: 

        '''
        if not source_config:
            return source_config

        try:
            source_config_obj = json.loads(source_config)

            if u'validator_profiles' in source_config_obj:
                if not isinstance(source_config_obj[u'validator_profiles'], list):
                    raise ValueError(u'validator_profiles must be a list')

                # Check if all profiles exist
                existing_profiles = [v.name for v in all_validators]
                unknown_profiles = set(source_config_obj[u'validator_profiles']) - set(
                    existing_profiles)

                if len(unknown_profiles) > 0:
                    raise ValueError(u'Unknown validation profile(s): %s' % u','.join(
                        unknown_profiles))

            if u'default_tags' in source_config_obj:
                if not isinstance(source_config_obj[u'default_tags'], list):
                    raise ValueError(u'default_tags must be a list')

            if u'default_extras' in source_config_obj:
                if not isinstance(source_config_obj[u'default_extras'], dict):
                    raise ValueError(u'default_extras must be a dictionary')

            for key in (u'override_extras'):
                if key in source_config_obj:
                    if not isinstance(source_config_obj[key], bool):
                        raise ValueError(u'%s must be boolean' % key)

        except ValueError, e:
            raise e

        return source_config

    ## SpatialHarvester

    def get_package_dict(self, iso_values, harvest_object):
        '''Constructs a package_dict suitable to be passed to package_create or
        package_update. See documentation on
        ckan.logic.action.create.package_create for more details
        
        Extensions willing to modify the dict should do so implementing the
        ISpatialHarvester interface
        
            import ckan.plugins as p
            from ckanext.spatial.interfaces import ISpatialHarvester
        
            class MyHarvester(p.SingletonPlugin):
        
                p.implements(ISpatialHarvester, inherit=True)
        
                def get_package_dict(self, context, data_dict):
        
                    package_dict = data_dict['package_dict']
        
                    package_dict['extras'].append(
                        {'key': 'my-custom-extra', 'value': 'my-custom-value'}
                    )
        
                    return package_dict
        
        If a dict is not returned by this function, the import stage will be cancelled.

        :param iso_values: Dictionary with parsed values from the ISO 19139
            XML document
        :type iso_values: dict
        :param harvest_object: HarvestObject domain object (with access to
            job and source objects)
        :type harvest_object: HarvestObject
        :returns: A dataset dictionary (package_dict)
        :rtype: dict

        '''

        tags = []
        if u'tags' in iso_values:
            for tag in iso_values[u'tags']:
                tag = tag[:50] if len(tag) > 50 else tag
                tags.append({
                    u'name': tag
                    })

        # Add default_tags from config
        default_tags = self.source_config.get(u'default_tags', [])
        if default_tags:
            for tag in default_tags:
                tags.append({
                    u'name': tag
                    })

        package_dict = {
            u'title': iso_values[u'title'],
            u'notes': iso_values[u'abstract'],
            u'tags': tags,
            u'resources': [],
            }

        # We need to get the owner organization (if any) from the harvest
        # source dataset
        source_dataset = model.Package.get(harvest_object.source.id)
        if source_dataset.owner_org:
            package_dict[u'owner_org'] = source_dataset.owner_org

        # Package name
        package = harvest_object.package
        if package is None or package.title != iso_values[u'title']:
            name = self._gen_new_name(iso_values[u'title'])
            if not name:
                name = self._gen_new_name(str(iso_values[u'guid']))
            if not name:
                raise Exception(
                    u'Could not generate a unique name from the title or the GUID. '
                    u'Please choose a more unique title.')
            package_dict[u'name'] = name
        else:
            package_dict[u'name'] = package.name

        extras = {
            u'guid': harvest_object.guid,
            u'spatial_harvester': True,
            }

        # Just add some of the metadata as extras, not the whole lot
        for name in [
            # Essentials
            u'spatial-reference-system',
            u'guid',
            # Usefuls
            u'dataset-reference-date',
            u'metadata-language',  # Language
            u'metadata-date',  # Released
            u'coupled-resource',
            u'contact-email',
            u'frequency-of-update',
            u'spatial-data-service-type',
            ]:
            extras[name] = iso_values[name]

        if len(iso_values.get(u'progress', [])):
            extras[u'progress'] = iso_values[u'progress'][0]
        else:
            extras[u'progress'] = u''

        if len(iso_values.get(u'resource-type', [])):
            extras[u'resource-type'] = iso_values[u'resource-type'][0]
        else:
            extras[u'resource-type'] = u''

        extras[u'licence'] = iso_values.get(u'use-constraints', u'')

        def _extract_first_license_url(licences):
            '''

            :param licences: 

            '''
            for licence in licences:
                o = urlparse(licence)
                if o.scheme and o.netloc:
                    return licence
            return None

        if len(extras[u'licence']):
            license_url_extracted = _extract_first_license_url(extras[u'licence'])
            if license_url_extracted:
                extras[u'licence_url'] = license_url_extracted

        # Metadata license ID check for package
        use_constraints = iso_values.get(u'use-constraints')
        if use_constraints:

            context = {
                u'user': self._get_user_name()
                }
            license_list = toolkit.get_action(u'license_list')(context, {})

            for constraint in use_constraints:
                package_license = None

                for license in license_list:
                    if constraint.lower() == license.get(
                            u'id') or constraint == license.get(u'url'):
                        package_license = license.get(u'id')
                        break

                if package_license:
                    package_dict[u'license_id'] = package_license
                    break

        extras[u'access_constraints'] = iso_values.get(u'limitations-on-public-access',
                                                       u'')

        # Grpahic preview
        browse_graphic = iso_values.get(u'browse-graphic')
        if browse_graphic:
            browse_graphic = browse_graphic[0]
            extras[u'graphic-preview-file'] = browse_graphic.get(u'file')
            if browse_graphic.get(u'description'):
                extras[u'graphic-preview-description'] = browse_graphic.get(
                    u'description')
            if browse_graphic.get(u'type'):
                extras[u'graphic-preview-type'] = browse_graphic.get(u'type')

        for key in [u'temporal-extent-begin', u'temporal-extent-end']:
            if len(iso_values[key]) > 0:
                extras[key] = iso_values[key][0]

        # Save responsible organization roles
        if iso_values[u'responsible-organisation']:
            parties = {}
            for party in iso_values[u'responsible-organisation']:
                if party[u'organisation-name'] in parties:
                    if not party[u'role'] in parties[party[u'organisation-name']]:
                        parties[party[u'organisation-name']].append(party[u'role'])
                else:
                    parties[party[u'organisation-name']] = [party[u'role']]
            extras[u'responsible-party'] = [{
                u'name': k,
                u'roles': v
                } for k, v in parties.iteritems()]

        if len(iso_values[u'bbox']) > 0:
            bbox = iso_values[u'bbox'][0]
            extras[u'bbox-east-long'] = bbox[u'east']
            extras[u'bbox-north-lat'] = bbox[u'north']
            extras[u'bbox-south-lat'] = bbox[u'south']
            extras[u'bbox-west-long'] = bbox[u'west']

            try:
                xmin = float(bbox[u'west'])
                xmax = float(bbox[u'east'])
                ymin = float(bbox[u'south'])
                ymax = float(bbox[u'north'])
            except ValueError, e:
                self._save_object_error(
                    u'Error parsing bounding box value: {0}'.format(str(e)),
                    harvest_object, u'Import')
            else:
                # Construct a GeoJSON extent so ckanext-spatial can register the
                # extent geometry

                # Some publishers define the same two corners for the bbox (ie a point),
                # that causes problems in the search if stored as polygon
                if xmin == xmax or ymin == ymax:
                    extent_string = Template(
                        u'{"type": "Point", "coordinates": [$x, $y]}').substitute(
                        x=xmin, y=ymin
                        )
                    self._save_object_error(u'Point extent defined instead of polygon',
                                            harvest_object, u'Import')
                else:
                    extent_string = self.extent_template.substitute(
                        xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax
                        )

                extras[u'spatial'] = extent_string.strip()
        else:
            log.debug(u'No spatial extent defined for this object')

        resource_locators = iso_values.get(u'resource-locator', []) + \
                            iso_values.get(u'resource-locator-identification', [])

        if len(resource_locators):
            for resource_locator in resource_locators:
                url = resource_locator.get(u'url', u'').strip()
                if url:
                    resource = {}
                    resource[u'format'] = guess_resource_format(url)
                    if resource[u'format'] == u'wms' and toolkit.config.get(
                            u'ckanext.spatial.harvest.validate_wms', False):
                        # Check if the service is a view service
                        test_url = url.split(u'?')[0] if u'?' in url else url
                        if self._is_wms(test_url):
                            resource[u'verified'] = True
                            resource[u'verified_date'] = datetime.now().isoformat()

                    resource.update(
                        {
                            u'url': url,
                            u'name': resource_locator.get(u'name') or toolkit._(
                                u'Unnamed resource'),
                            u'description': resource_locator.get(u'description') or u'',
                            u'resource_locator_protocol': resource_locator.get(
                                u'protocol') or u'',
                            u'resource_locator_function': resource_locator.get(
                                u'function') or u'',
                            })
                    package_dict[u'resources'].append(resource)

        # Add default_extras from config
        default_extras = self.source_config.get(u'default_extras', {})
        if default_extras:
            override_extras = self.source_config.get(u'override_extras', False)
            for key, value in default_extras.iteritems():
                log.debug(u'Processing extra %s', key)
                if not key in extras or override_extras:
                    # Look for replacement strings
                    if isinstance(value, basestring):
                        value = value.format(
                            harvest_source_id=harvest_object.job.source.id,
                            harvest_source_url=harvest_object.job.source.url.strip('/'),
                            harvest_source_title=harvest_object.job.source.title,
                            harvest_job_id=harvest_object.job.id,
                            harvest_object_id=harvest_object.id)
                    extras[key] = value

        extras_as_dict = []
        for key, value in extras.iteritems():
            if isinstance(value, (list, dict)):
                extras_as_dict.append({
                    u'key': key,
                    u'value': json.dumps(value)
                    })
            else:
                extras_as_dict.append({
                    u'key': key,
                    u'value': value
                    })

        package_dict[u'extras'] = extras_as_dict

        return package_dict

    def transform_to_iso(self, original_document, original_format, harvest_object):
        '''DEPRECATED: Use the transform_to_iso method of the ISpatialHarvester
        interface

        :param original_document: 
        :param original_format: 
        :param harvest_object: 

        '''
        self.__base_transform_to_iso_called = True
        return None

    def import_stage(self, harvest_object):
        '''

        :param harvest_object: 

        '''
        context = {
            u'user': self._get_user_name(),
            }

        log = logging.getLogger(__name__ + u'.import')
        log.debug(u'Import stage for harvest object: %s', harvest_object.id)

        if not harvest_object:
            log.error(u'No harvest object received')
            return False

        self._set_source_config(harvest_object.source.config)

        if self.force_import:
            status = u'change'
        else:
            status = self._get_object_extra(harvest_object, u'status')

        # Get the last harvested object (if any)
        previous_object = model.Session.query(HarvestObject) \
            .filter(HarvestObject.guid == harvest_object.guid) \
            .filter(HarvestObject.current == True) \
            .first()

        if status == u'delete':
            # Delete package
            context.update({
                u'ignore_auth': True,
                })
            toolkit.get_action(u'package_delete')(context, {
                u'id': harvest_object.package_id
                })
            log.info(
                u'Deleted package {0} with guid {1}'.format(harvest_object.package_id,
                                                            harvest_object.guid))

            return True

        # Check if it is a non ISO document
        original_document = self._get_object_extra(harvest_object, u'original_document')
        original_format = self._get_object_extra(harvest_object, u'original_format')
        if original_document and original_format:
            # DEPRECATED use the ISpatialHarvester interface method
            self.__base_transform_to_iso_called = False
            content = self.transform_to_iso(original_document, original_format,
                                            harvest_object)
            if not self.__base_transform_to_iso_called:
                log.warn(
                    u'Deprecation warning: calling transform_to_iso directly is '
                    u'deprecated. ' +
                    u'Please use the ISpatialHarvester interface method instead.')

            for harvester in PluginImplementations(ISpatialHarvester):
                content = harvester.transform_to_iso(original_document, original_format,
                                                     harvest_object)

            if content:
                harvest_object.content = content
            else:
                self._save_object_error(u'Transformation to ISO failed', harvest_object,
                                        u'Import')
                return False
        else:
            if harvest_object.content is None:
                self._save_object_error(
                    u'Empty content for object {0}'.format(harvest_object.id),
                    harvest_object, u'Import')
                return False

            # Validate ISO document
            is_valid, profile, errors = self._validate_document(harvest_object.content,
                                                                harvest_object)
            if not is_valid:
                # If validation errors were found, import will stop unless
                # configuration per source or per instance says otherwise
                continue_import = toolkit.asbool(
                    toolkit.config.get(
                        u'ckanext.spatial.harvest.continue_on_validation_errors',
                        False)) or \
                                  self.source_config.get(
                                      u'continue_on_validation_errors')
                if not continue_import:
                    return False

        # Parse ISO document
        try:

            iso_parser = ISODocument(harvest_object.content)
            iso_values = iso_parser.read_values()
        except Exception, e:
            self._save_object_error(
                u'Error parsing ISO document for object {0}: {1}'.format(
                    harvest_object.id, str(e)),
                harvest_object, u'Import')
            return False

        # Flag previous object as not current anymore
        if previous_object and not self.force_import:
            previous_object.current = False
            previous_object.add()

        # Update GUID with the one on the document
        iso_guid = iso_values[u'guid']
        if iso_guid and harvest_object.guid != iso_guid:
            # First make sure there already aren't current objects
            # with the same guid
            existing_object = model.Session.query(HarvestObject.id) \
                .filter(HarvestObject.guid == iso_guid) \
                .filter(HarvestObject.current == True) \
                .first()
            if existing_object:
                self._save_object_error(
                    u'Object {0} already has this guid {1}'.format(existing_object.id,
                                                                   iso_guid),
                    harvest_object, u'Import')
                return False

            harvest_object.guid = iso_guid
            harvest_object.add()

        # Generate GUID if not present (i.e. it's a manual import)
        if not harvest_object.guid:
            m = hashlib.md5()
            m.update(harvest_object.content.encode(u'utf8', u'ignore'))
            harvest_object.guid = m.hexdigest()
            harvest_object.add()

        # Get document modified date
        try:
            metadata_modified_date = dateutil.parser.parse(iso_values[u'metadata-date'],
                                                           ignoretz=True)
        except ValueError:
            self._save_object_error(
                u'Could not extract reference date for object {0} ({1})'
                    .format(harvest_object.id, iso_values[u'metadata-date']),
                harvest_object,
                u'Import')
            return False

        harvest_object.metadata_modified_date = metadata_modified_date
        harvest_object.add()

        # Build the package dict
        package_dict = self.get_package_dict(iso_values, harvest_object)
        for harvester in PluginImplementations(ISpatialHarvester):
            package_dict = harvester.get_package_dict(context, {
                u'package_dict': package_dict,
                u'iso_values': iso_values,
                u'xml_tree': iso_parser.xml_tree,
                u'harvest_object': harvest_object,
                })
        if not package_dict:
            log.error(u'No package dict returned, aborting import for object {0}'.format(
                harvest_object.id))
            return False

        # Create / update the package
        context.update({
            u'extras_as_string': True,
            u'api_version': u'2',
            u'return_id_only': True
            })

        if self._site_user and context[u'user'] == self._site_user[u'name']:
            context[u'ignore_auth'] = True

        # The default package schema does not like Upper case tags
        tag_schema = logic.schema.default_tags_schema()
        tag_schema[u'name'] = [toolkit.get_validator(u'not_empty'), unicode]

        # Flag this object as the current one
        harvest_object.current = True
        harvest_object.add()

        if status == u'new':
            package_schema = logic.schema.default_create_package_schema()
            package_schema[u'tags'] = tag_schema
            context[u'schema'] = package_schema

            # We need to explicitly provide a package ID, otherwise ckanext-spatial
            # won't be be able to link the extent to the package.
            package_dict[u'id'] = unicode(uuid.uuid4())
            package_schema[u'id'] = [unicode]

            # Save reference to the package on the object
            harvest_object.package_id = package_dict[u'id']
            harvest_object.add()
            # Defer constraints and flush so the dataset can be indexed with
            # the harvest object id (on the after_show hook from the harvester
            # plugin)
            model.Session.execute(
                u'SET CONSTRAINTS harvest_object_package_id_fkey DEFERRED')
            model.Session.flush()

            try:
                package_id = toolkit.get_action(u'package_create')(context,
                                                                   package_dict)
                log.info(u'Created new package %s with guid %s', package_id,
                         harvest_object.guid)
            except toolkit.ValidationError, e:
                self._save_object_error(u'Validation Error: %s' % str(e.error_summary),
                                        harvest_object, u'Import')
                return False

        elif status == u'change':

            # Check if the modified date is more recent
            if not self.force_import and previous_object and \
                    harvest_object.metadata_modified_date <= \
                    previous_object.metadata_modified_date:

                # Assign the previous job id to the new object to
                # avoid losing history
                harvest_object.harvest_job_id = previous_object.job.id
                harvest_object.add()

                # Delete the previous object to avoid cluttering the object table
                previous_object.delete()

                # Reindex the corresponding package to update the reference to the
                # harvest object
                if ((toolkit.config.get(u'ckanext.spatial.harvest.reindex_unchanged',
                                        True) != u'False'
                     or self.source_config.get(u'reindex_unchanged') != u'False')
                        and harvest_object.package_id):
                    context.update({
                        u'validate': False,
                        u'ignore_auth': True
                        })
                    try:
                        package_dict = toolkit.get_action(u'package_show')(
                            context, {
                                u'id': harvest_object.package_id
                                })
                    except toolkit.ObjectNotFound:
                        pass
                    else:
                        for extra in package_dict.get(u'extras', []):
                            if extra[u'key'] == u'harvest_object_id':
                                extra[u'value'] = harvest_object.id
                        if package_dict:
                            package_index = PackageSearchIndex()
                            package_index.index_package(package_dict)

                log.info(u'Document with GUID %s unchanged, skipping...' % (
                    harvest_object.guid))
            else:
                package_schema = logic.schema.default_update_package_schema()
                package_schema[u'tags'] = tag_schema
                context[u'schema'] = package_schema

                package_dict[u'id'] = harvest_object.package_id
                try:
                    package_id = toolkit.get_action(u'package_update')(context,
                                                                       package_dict)
                    log.info(u'Updated package %s with guid %s', package_id,
                             harvest_object.guid)
                except toolkit.ValidationError, e:
                    self._save_object_error(
                        u'Validation Error: %s' % str(e.error_summary), harvest_object,
                        u'Import')
                    return False

        model.Session.commit()

        return True

    ##

    def _is_wms(self, url):
        '''Checks if the provided URL actually points to a Web Map Service.
        Uses owslib WMS reader to parse the response.

        :param url: 

        '''
        try:
            capabilities_url = wms.WMSCapabilitiesReader().capabilities_url(url)
            res = urllib2.urlopen(capabilities_url, None, 10)
            xml = res.read()

            s = wms.WebMapService(url, xml=xml)
            return isinstance(s.contents, dict) and s.contents != {}
        except Exception, e:
            log.error(u'WMS check for %s failed with exception: %s' % (url, str(e)))
        return False

    def _get_object_extra(self, harvest_object, key):
        '''Helper function for retrieving the value from a harvest object extra,
        given the key

        :param harvest_object: 
        :param key: 

        '''
        for extra in harvest_object.extras:
            if extra.key == key:
                return extra.value
        return None

    def _set_source_config(self, config_str):
        '''Loads the source configuration JSON object into a dict for
        convenient access

        :param config_str: 

        '''
        if config_str:
            self.source_config = json.loads(config_str)
            log.debug(u'Using config: %r', self.source_config)
        else:
            self.source_config = {}

    def _get_validator(self):
        '''Returns the validator object using the relevant profiles
        
        The profiles to be used are assigned in the following order:
        
        1. 'validator_profiles' property of the harvest source config object
        2. 'ckan.spatial.validator.profiles' configuration option in the ini file
        3. Default value as defined in DEFAULT_VALIDATOR_PROFILES


        '''
        if not hasattr(self, u'_validator'):
            if hasattr(self, u'source_config') and self.source_config.get(
                    u'validator_profiles', None):
                profiles = self.source_config.get(u'validator_profiles')
            elif toolkit.config.get(u'ckan.spatial.validator.profiles', None):
                profiles = [
                    x.strip() for x in
                    toolkit.config.get(u'ckan.spatial.validator.profiles').split(u',')
                    ]
            else:
                profiles = DEFAULT_VALIDATOR_PROFILES
            self._validator = Validators(profiles=profiles)

            # Add any custom validators from extensions
            for plugin_with_validators in PluginImplementations(ISpatialHarvester):
                custom_validators = plugin_with_validators.get_validators()
                for custom_validator in custom_validators:
                    if custom_validator not in all_validators:
                        self._validator.add_validator(custom_validator)

        return self._validator

    def _get_user_name(self):
        '''Returns the name of the user that will perform the harvesting actions
        (deleting, updating and creating datasets)
        
        By default this will be the internal site admin user. This is the
        recommended setting, but if necessary it can be overridden with the
        `ckanext.spatial.harvest.user_name` config option, eg to support the
        old hardcoded 'harvest' user:
        
           ckanext.spatial.harvest.user_name = harvest


        '''
        if self._user_name:
            return self._user_name

        context = {
            u'ignore_auth': True,
            u'defer_commit': True,  # See ckan/ckan#1714
            }
        self._site_user = toolkit.get_action(u'get_site_user')(context, {})

        config_user_name = toolkit.config.get(u'ckanext.spatial.harvest.user_name')
        if config_user_name:
            self._user_name = config_user_name
        else:
            self._user_name = self._site_user[u'name']

        return self._user_name

    def _get_content(self, url):
        '''DEPRECATED: Use _get_content_as_unicode instead

        :param url: 

        '''
        url = url.replace(u' ', u'%20')
        http_response = urllib2.urlopen(url)
        return http_response.read()

    def _get_content_as_unicode(self, url):
        '''Get remote content as unicode.
        
        We let requests handle the conversion [1] , which will use the
        content-type header first or chardet if the header is missing
        (requests uses its own embedded chardet version).
        
        As we will be storing and serving the contents as unicode, we actually
        replace the original XML encoding declaration with an UTF-8 one.
        
        
        [1] http://github.com/kennethreitz/requests/blob
        /63243b1e3b435c7736acf1e51c0f6fa6666d861d/requests/models.py#L811

        :param url: 

        '''
        url = url.replace(u' ', u'%20')
        response = requests.get(url, timeout=10)

        content = response.text

        # Remove original XML declaration
        content = re.sub(u'<\?xml(.*)\?>', u'', content)

        # Get rid of the BOM and other rubbish at the beginning of the file
        content = re.sub(u'.*?<', u'<', content, 1)
        content = content[content.index(u'<'):]

        return content

    def _validate_document(self, document_string, harvest_object, validator=None):
        '''Validates an XML document with the default, or if present, the
        provided validators.
        
        It will create a HarvestObjectError for each validation error found,
        so they can be shown properly on the frontend.
        
        Returns a tuple, with a boolean showing whether the validation passed
        or not, the profile used and a list of errors (tuples with error
        message and error lines if present).

        :param document_string: 
        :param harvest_object: 
        :param validator:  (Default value = None)

        '''
        if not validator:
            validator = self._get_validator()

        document_string = re.sub(u'<\?xml(.*)\?>', u'', document_string)

        try:
            xml = etree.fromstring(document_string)
        except etree.XMLSyntaxError, e:
            self._save_object_error(u'Could not parse XML file: {0}'.format(str(e)),
                                    harvest_object, u'Import')
            return False, None, []

        valid, profile, errors = validator.is_valid(xml)
        if not valid:
            log.error(u'Validation errors found using profile {0} for object with GUID '
                      u'{1}'.format(profile, harvest_object.guid))
            for error in errors:
                self._save_object_error(error[0], harvest_object, u'Validation',
                                        line=error[1])

        return valid, profile, errors

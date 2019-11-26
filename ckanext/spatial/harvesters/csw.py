#!/usr/bin/env python
# encoding: utf-8

import logging
import urllib
import urlparse

import re
from ckanext.harvest.interfaces import IHarvester
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra as HOExtra
from ckanext.spatial.harvesters.base import SpatialHarvester, text_traceback
from ckanext.spatial.lib.csw_client import CswService

from ckan import model
from ckan.plugins import SingletonPlugin, implements


class CSWHarvester(SpatialHarvester, SingletonPlugin):
    '''A Harvester for CSW servers'''
    implements(IHarvester)

    csw = None

    def info(self):
        ''' '''
        return {
            u'name': u'csw',
            u'title': u'CSW Server',
            u'description': u'A server that implements OGC\'s Catalog Service for the '
                            u'Web (CSW) standard'
            }

    def get_original_url(self, harvest_object_id):
        '''

        :param harvest_object_id: 

        '''
        obj = model.Session.query(HarvestObject). \
            filter(HarvestObject.id == harvest_object_id). \
            first()

        parts = urlparse.urlparse(obj.source.url)

        params = {
            u'SERVICE': u'CSW',
            u'VERSION': u'2.0.2',
            u'REQUEST': u'GetRecordById',
            u'OUTPUTSCHEMA': u'http://www.isotc211.org/2005/gmd',
            u'OUTPUTFORMAT': u'application/xml',
            u'ID': obj.guid
            }

        url = urlparse.urlunparse((
            parts.scheme,
            parts.netloc,
            parts.path,
            None,
            urllib.urlencode(params),
            None
            ))

        return url

    def output_schema(self):
        ''' '''
        return u'gmd'

    def gather_stage(self, harvest_job):
        '''

        :param harvest_job: 

        '''
        log = logging.getLogger(__name__ + u'.CSW.gather')
        log.debug(u'CswHarvester gather_stage for job: %r', harvest_job)
        # Get source URL
        url = harvest_job.source.url

        self._set_source_config(harvest_job.source.config)

        try:
            self._setup_csw_client(url)
        except Exception, e:
            self._save_gather_error(u'Error contacting the CSW server: %s' % e,
                                    harvest_job)
            return None

        query = model.Session.query(HarvestObject.guid, HarvestObject.package_id). \
            filter(HarvestObject.current == True). \
            filter(HarvestObject.harvest_source_id == harvest_job.source.id)
        guid_to_package_id = {}

        for guid, package_id in query:
            guid_to_package_id[guid] = package_id

        guids_in_db = set(guid_to_package_id.keys())

        # extract cql filter if any
        cql = self.source_config.get(u'cql')

        log.debug(u'Starting gathering for %s' % url)
        guids_in_harvest = set()
        try:
            for identifier in self.csw.getidentifiers(page=10,
                                                      outputschema=self.output_schema(),
                                                      cql=cql):
                try:
                    log.info(u'Got identifier %s from the CSW', identifier)
                    if identifier is None:
                        log.error(
                            u'CSW returned identifier %r, skipping...' % identifier)
                        continue

                    guids_in_harvest.add(identifier)
                except Exception, e:
                    self._save_gather_error(
                        u'Error for the identifier %s [%r]' % (identifier, e),
                        harvest_job)
                    continue


        except Exception, e:
            log.error(u'Exception: %s' % text_traceback())
            self._save_gather_error(
                u'Error gathering the identifiers from the CSW server [%s]' % str(e),
                harvest_job)
            return None

        new = guids_in_harvest - guids_in_db
        delete = guids_in_db - guids_in_harvest
        change = guids_in_db & guids_in_harvest

        ids = []
        for guid in new:
            obj = HarvestObject(guid=guid, job=harvest_job,
                                extras=[HOExtra(key=u'status', value=u'new')])
            obj.save()
            ids.append(obj.id)
        for guid in change:
            obj = HarvestObject(guid=guid, job=harvest_job,
                                package_id=guid_to_package_id[guid],
                                extras=[HOExtra(key=u'status', value=u'change')])
            obj.save()
            ids.append(obj.id)
        for guid in delete:
            obj = HarvestObject(guid=guid, job=harvest_job,
                                package_id=guid_to_package_id[guid],
                                extras=[HOExtra(key=u'status', value=u'delete')])
            model.Session.query(HarvestObject). \
                filter_by(guid=guid). \
                update({
                u'current': False
                }, False)
            obj.save()
            ids.append(obj.id)

        if len(ids) == 0:
            self._save_gather_error(u'No records received from the CSW server',
                                    harvest_job)
            return None

        return ids

    def fetch_stage(self, harvest_object):
        '''

        :param harvest_object: 

        '''

        # Check harvest object status
        status = self._get_object_extra(harvest_object, u'status')

        if status == u'delete':
            # No need to fetch anything, just pass to the import stage
            return True

        log = logging.getLogger(__name__ + u'.CSW.fetch')
        log.debug(u'CswHarvester fetch_stage for object: %s', harvest_object.id)

        url = harvest_object.source.url
        try:
            self._setup_csw_client(url)
        except Exception, e:
            self._save_object_error(u'Error contacting the CSW server: %s' % e,
                                    harvest_object)
            return False

        identifier = harvest_object.guid
        try:
            record = self.csw.getrecordbyid([identifier],
                                            outputschema=self.output_schema())
        except Exception, e:
            self._save_object_error(
                u'Error getting the CSW record with GUID %s' % identifier,
                harvest_object)
            return False

        if record is None:
            self._save_object_error(u'Empty record for GUID %s' % identifier,
                                    harvest_object)
            return False

        try:
            # Save the fetch contents in the HarvestObject
            # Contents come from csw_client already declared and encoded as utf-8
            # Remove original XML declaration
            content = re.sub(u'<\?xml(.*)\?>', u'', record[u'xml'])

            harvest_object.content = content.strip()
            harvest_object.save()
        except Exception, e:
            self._save_object_error(u'Error saving the harvest object for GUID %s ['
                                    u'%r]' % (identifier, e), harvest_object)
            return False

        log.debug(u'XML content saved (len %s)', len(record[u'xml']))
        return True

    def _setup_csw_client(self, url):
        '''

        :param url: 

        '''
        self.csw = CswService(url)

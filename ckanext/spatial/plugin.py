#!/usr/bin/env python
# encoding: utf-8

import json
import mimetypes
from logging import getLogger

import os
import re

from ckan.plugins import SingletonPlugin, implements, interfaces, toolkit


def check_geoalchemy_requirement():
    '''Checks if a suitable geoalchemy version installed
    
       Checks if geoalchemy2 is present when using CKAN >= 2.3, and raises
       an ImportError otherwise so users can upgrade manually.


    '''

    msg = (u'This version of ckanext-spatial requires {0}. ' +
           u'Please install it by running `pip install {0}`.\n' +
           u'For more details see the "Troubleshooting" section of the ' +
           u'install documentation')

    if toolkit.check_ckan_version(min_version=u'2.3'):
        try:
            import geoalchemy2
        except ImportError:
            raise ImportError(msg.format(u'geoalchemy2'))
    else:
        try:
            import geoalchemy
        except ImportError:
            raise ImportError(msg.format(u'geoalchemy'))


check_geoalchemy_requirement()

log = getLogger(__name__)


def package_error_summary(error_dict):
    '''Do some i18n stuff on the error_dict keys

    :param error_dict: 

    '''

    def prettify(field_name):
        '''

        :param field_name: 

        '''
        field_name = re.sub(u'(?<!\w)[Uu]rl(?!\w)', u'URL',
                            field_name.replace(u'_', u' ').capitalize())
        return toolkit._(field_name.replace(u'_', u' '))

    summary = {}
    for key, error in error_dict.iteritems():
        if key == u'resources':
            summary[toolkit._(u'Resources')] = toolkit._(
                u'Package resource(s) invalid')
        elif key == u'extras':
            summary[toolkit._(u'Extras')] = toolkit._(u'Missing Value')
        elif key == u'extras_validation':
            summary[toolkit._(u'Extras')] = error[0]
        else:
            summary[toolkit._(prettify(key))] = error[0]
    return summary


class SpatialMetadata(SingletonPlugin):
    ''' '''

    implements(interfaces.IPackageController, inherit=True)
    implements(interfaces.IConfigurable, inherit=True)
    implements(interfaces.IConfigurer, inherit=True)
    implements(interfaces.ITemplateHelpers, inherit=True)

    def configure(self, config):
        '''

        :param config: 

        '''
        from ckanext.spatial.model.package_extent import setup as setup_model

        if not toolkit.asbool(config.get(u'ckan.spatial.testing', u'False')):
            log.debug(u'Setting up the spatial model')
            setup_model()

    def update_config(self, config):
        '''Set up the resource library, public directory and
        template directory for all the spatial extensions

        :param config: 

        '''
        toolkit.add_public_directory(config, u'public')
        toolkit.add_template_directory(config, u'templates')
        toolkit.add_resource(u'public', u'ckanext-spatial')

        # Add media types for common extensions not included in the mimetypes
        # module
        mimetypes.add_type(u'application/json', u'.geojson')
        mimetypes.add_type(u'application/gml+xml', u'.gml')

    def create(self, package):
        '''

        :param package: 

        '''
        self.check_spatial_extra(package)

    def edit(self, package):
        '''

        :param package: 

        '''
        self.check_spatial_extra(package)

    def check_spatial_extra(self, package):
        '''For a given package, looks at the spatial extent (as given in the
        extra "spatial" in GeoJSON format) and records it in PostGIS.

        :param package: 

        '''
        from ckanext.spatial.lib import save_package_extent

        if not package.id:
            log.warning(
                u'Couldn\'t store spatial extent because no id was provided for the '
                u'package')
            return

        # TODO: deleted extra
        for extra in package.extras_list:
            if extra.key == u'spatial':
                if extra.state == u'active' and extra.value:
                    try:
                        log.debug(u'Received: %r' % extra.value)
                        geometry = json.loads(extra.value)
                    except ValueError, e:
                        error_dict = {
                            u'spatial': [u'Error decoding JSON object: %s' % str(e)]
                            }
                        raise toolkit.ValidationError(error_dict,
                                                      error_summary=package_error_summary(
                                                          error_dict))
                    except TypeError, e:
                        error_dict = {
                            u'spatial': [u'Error decoding JSON object: %s' % str(e)]
                            }
                        raise toolkit.ValidationError(error_dict,
                                                      error_summary=package_error_summary(
                                                          error_dict))

                    try:
                        save_package_extent(package.id, geometry)

                    except ValueError, e:
                        error_dict = {
                            u'spatial': [u'Error creating geometry: %s' % str(e)]
                            }
                        raise toolkit.ValidationError(error_dict,
                                                      error_summary=package_error_summary(
                                                          error_dict))
                    except Exception, e:
                        if bool(os.getenv(u'DEBUG')):
                            raise
                        error_dict = {
                            u'spatial': [u'Error: %s' % str(e)]
                            }
                        raise toolkit.ValidationError(error_dict,
                                                      error_summary=package_error_summary(
                                                          error_dict))

                elif (
                        extra.state == u'active' and not extra.value) or extra.state \
                        == u'deleted':
                    # Delete extent from table
                    save_package_extent(package.id, None)

                break

    def delete(self, package):
        '''

        :param package: 

        '''
        from ckanext.spatial.lib import save_package_extent
        save_package_extent(package.id, None)

    ## ITemplateHelpers

    def get_helpers(self):
        ''' '''
        from ckanext.spatial import helpers as spatial_helpers
        return {
            u'get_reference_date': spatial_helpers.get_reference_date,
            u'get_responsible_party': spatial_helpers.get_responsible_party,
            u'get_common_map_config': spatial_helpers.get_common_map_config,
            }


class SpatialQuery(SingletonPlugin):
    ''' '''

    implements(interfaces.IRoutes, inherit=True)
    implements(interfaces.IPackageController, inherit=True)
    implements(interfaces.IConfigurable, inherit=True)

    search_backend = None

    def configure(self, config):
        '''

        :param config: 

        '''

        self.search_backend = config.get(u'ckanext.spatial.search_backend', u'postgis')
        if self.search_backend != u'postgis' and not toolkit.check_ckan_version(
                u'2.0.1'):
            msg = u'The Solr backends for the spatial search require CKAN 2.0.1 or ' \
                  u'higher. ' + \
                  u'Please upgrade CKAN or select the \'postgis\' backend.'
            raise toolkit.CkanVersionException(msg)

    def before_map(self, map):
        '''

        :param map: 

        '''

        map.connect(u'api_spatial_query', '/api/2/search/{register:dataset|package}/geo',
                    controller=u'ckanext.spatial.controllers.api:ApiController',
                    action=u'spatial_query')
        return map

    def before_index(self, pkg_dict):
        '''

        :param pkg_dict: 

        '''
        import shapely.geometry

        if pkg_dict.get(u'extras_spatial', None) and self.search_backend in (
                u'solr', u'solr-spatial-field'):
            try:
                geometry = json.loads(pkg_dict[u'extras_spatial'])
            except ValueError, e:
                log.error(u'Geometry not valid GeoJSON, not indexing')
                return pkg_dict

            if self.search_backend == u'solr':
                # Only bbox supported for this backend
                if not (geometry[u'type'] == u'Polygon'
                        and len(geometry[u'coordinates']) == 1
                        and len(geometry[u'coordinates'][0]) == 5):
                    log.error(
                        u'Solr backend only supports bboxes (Polygons with 5 points), '
                        u'ignoring geometry {0}'.format(
                            pkg_dict[u'extras_spatial']))
                    return pkg_dict

                coords = geometry[u'coordinates']
                pkg_dict[u'maxy'] = max(coords[0][2][1], coords[0][0][1])
                pkg_dict[u'miny'] = min(coords[0][2][1], coords[0][0][1])
                pkg_dict[u'maxx'] = max(coords[0][2][0], coords[0][0][0])
                pkg_dict[u'minx'] = min(coords[0][2][0], coords[0][0][0])
                pkg_dict[u'bbox_area'] = (pkg_dict[u'maxx'] - pkg_dict[u'minx']) * \
                                         (pkg_dict[u'maxy'] - pkg_dict[u'miny'])

            elif self.search_backend == u'solr-spatial-field':
                wkt = None

                # Check potential problems with bboxes
                if geometry[u'type'] == u'Polygon' \
                        and len(geometry[u'coordinates']) == 1 \
                        and len(geometry[u'coordinates'][0]) == 5:

                    # Check wrong bboxes (4 same points)
                    xs = [p[0] for p in geometry[u'coordinates'][0]]
                    ys = [p[1] for p in geometry[u'coordinates'][0]]

                    if xs.count(xs[0]) == 5 and ys.count(ys[0]) == 5:
                        wkt = u'POINT({x} {y})'.format(x=xs[0], y=ys[0])
                    else:
                        # Check if coordinates are defined counter-clockwise,
                        # otherwise we'll get wrong results from Solr
                        lr = shapely.geometry.polygon.LinearRing(
                            geometry[u'coordinates'][0])
                        if not lr.is_ccw:
                            lr.coords = list(lr.coords)[::-1]
                        polygon = shapely.geometry.polygon.Polygon(lr)
                        wkt = polygon.wkt

                if not wkt:
                    shape = shapely.geometry.asShape(geometry)
                    if not shape.is_valid:
                        log.error(u'Wrong geometry, not indexing')
                        return pkg_dict
                    wkt = shape.wkt

                pkg_dict[u'spatial_geom'] = wkt

        return pkg_dict

    def before_search(self, search_params):
        '''

        :param search_params: 

        '''
        from ckanext.spatial.lib import validate_bbox
        from ckan.lib.search import SearchError

        if search_params.get(u'extras', None) and search_params[u'extras'].get(
                u'ext_bbox', None):

            bbox = validate_bbox(search_params[u'extras'][u'ext_bbox'])
            if not bbox:
                raise SearchError(u'Wrong bounding box provided')

            # Adjust easting values
            while (bbox[u'minx'] < -180):
                bbox[u'minx'] += 360
                bbox[u'maxx'] += 360
            while (bbox[u'minx'] > 180):
                bbox[u'minx'] -= 360
                bbox[u'maxx'] -= 360

            if self.search_backend == u'solr':
                search_params = self._params_for_solr_search(bbox, search_params)
            elif self.search_backend == u'solr-spatial-field':
                search_params = self._params_for_solr_spatial_field_search(bbox,
                                                                           search_params)
            elif self.search_backend == u'postgis':
                search_params = self._params_for_postgis_search(bbox, search_params)

        return search_params

    def _params_for_solr_search(self, bbox, search_params):
        '''This will add the following parameters to the query:
        
            defType - edismax (We need to define EDisMax to use bf)
            bf - {function} A boost function to influence the score (thus
                 influencing the sorting). The algorithm can be basically defined as:
        
                    2 * X / Q + T
        
                 Where X is the intersection between the query area Q and the
                 target geometry T. It gives a ratio from 0 to 1 where 0 means
                 no overlap at all and 1 a perfect fit
        
             fq - Adds a filter that force the value returned by the previous
                  function to be between 0 and 1, effectively applying the
                  spatial filter.

        :param bbox: 
        :param search_params: 

        '''

        variables = dict(
            x11=bbox[u'minx'],
            x12=bbox[u'maxx'],
            y11=bbox[u'miny'],
            y12=bbox[u'maxy'],
            x21=u'minx',
            x22=u'maxx',
            y21=u'miny',
            y22=u'maxy',
            area_search=abs(bbox[u'maxx'] - bbox[u'minx']) * abs(
                bbox[u'maxy'] - bbox[u'miny'])
            )

        bf = u'''div(
                   mul(
                   mul(max(0, sub(min({x12},{x22}) , max({x11},{x21}))),
                       max(0, sub(min({y12},{y22}) , max({y11},{y21})))
                       ),
                   2),
                   add({area_search}, mul(sub({y22}, {y21}), sub({x22}, {x21})))
                )'''.format(**variables).replace(u'\n', u'').replace(u' ', u'')

        search_params[u'fq_list'] = [u'{!frange incl=false l=0 u=1}%s' % bf]

        search_params[u'bf'] = bf
        search_params[u'defType'] = u'edismax'

        return search_params

    def _params_for_solr_spatial_field_search(self, bbox, search_params):
        '''This will add an fq filter with the form:
        
            +spatial_geom:"Intersects(ENVELOPE({minx}, {miny}, {maxx}, {maxy}))

        :param bbox: 
        :param search_params: 

        '''
        search_params[u'fq_list'] = search_params.get(u'fq_list', [])
        search_params[u'fq_list'].append(
            u'+spatial_geom:"Intersects(ENVELOPE({minx}, {maxx}, {maxy}, {miny}))"'
                .format(minx=bbox[u'minx'], miny=bbox[u'miny'], maxx=bbox[u'maxx'],
                        maxy=bbox[u'maxy']))

        return search_params

    def _params_for_postgis_search(self, bbox, search_params):
        '''

        :param bbox: 
        :param search_params: 

        '''
        from ckanext.spatial.lib import bbox_query, bbox_query_ordered
        from ckan.lib.search import SearchError

        # Note: This will be deprecated at some point in favour of the
        # Solr 4 spatial sorting capabilities
        if search_params.get(u'sort') == u'spatial desc' and \
                toolkit.asbool(
                    toolkit.config.get(u'ckanext.spatial.use_postgis_sorting',
                                       u'False')):
            if search_params[u'q'] or search_params[u'fq']:
                raise SearchError(
                    u'Spatial ranking cannot be mixed with other search parameters')
                # ...because it is too inefficient to use SOLR to filter
                # results and return the entire set to this class and
                # after_search do the sorting and paging.
            extents = bbox_query_ordered(bbox)
            are_no_results = not extents
            search_params[u'extras'][u'ext_rows'] = search_params[u'rows']
            search_params[u'extras'][u'ext_start'] = search_params[u'start']
            # this SOLR query needs to return no actual results since
            # they are in the wrong order anyway. We just need this SOLR
            # query to get the count and facet counts.
            rows = 0
            search_params[u'sort'] = None  # SOLR should not sort.
            # Store the rankings of the results for this page, so for
            # after_search to construct the correctly sorted results
            rows = search_params[u'extras'][u'ext_rows'] = search_params[u'rows']
            start = search_params[u'extras'][u'ext_start'] = search_params[u'start']
            search_params[u'extras'][u'ext_spatial'] = [
                (extent.package_id, extent.spatial_ranking) \
                for extent in extents[start:start + rows]]
        else:
            extents = bbox_query(bbox)
            are_no_results = extents.count() == 0

        if are_no_results:
            # We don't need to perform the search
            search_params[u'abort_search'] = True
        else:
            # We'll perform the existing search but also filtering by the ids
            # of datasets within the bbox
            bbox_query_ids = [extent.package_id for extent in extents]

            q = search_params.get(u'q', u'').strip() or u'""'
            new_q = u'%s AND ' % q if q else u''
            new_q += u'(%s)' % u' OR '.join([u'id:%s' % id for id in bbox_query_ids])

            search_params[u'q'] = new_q

        return search_params

    def after_search(self, search_results, search_params):
        '''

        :param search_results: 
        :param search_params: 

        '''
        from ckan.lib.search import PackageSearchQuery

        # Note: This will be deprecated at some point in favour of the
        # Solr 4 spatial sorting capabilities

        if search_params.get(u'extras', {}).get(u'ext_spatial') and \
                toolkit.asbool(
                    toolkit.config.get(u'ckanext.spatial.use_postgis_sorting',
                                       u'False')):
            # Apply the spatial sort
            querier = PackageSearchQuery()
            pkgs = []
            for package_id, spatial_ranking in search_params[u'extras'][u'ext_spatial']:
                # get package from SOLR
                pkg = querier.get_index(package_id)[u'data_dict']
                pkgs.append(json.loads(pkg))
            search_results[u'results'] = pkgs
        return search_results


class HarvestMetadataApi(SingletonPlugin):
    '''Harvest Metadata API
    (previously called "InspireApi")
    
    A way for a user to view the harvested metadata XML, either as a raw file or
    styled to view in a web browser.


    '''
    implements(interfaces.IRoutes)

    def before_map(self, route_map):
        '''

        :param route_map: 

        '''
        controller = u'ckanext.spatial.controllers.api:HarvestMetadataApiController'

        # Showing the harvest object content is an action of the default
        # harvest plugin, so just redirect there
        route_map.redirect('/api/2/rest/harvestobject/{id:.*}/xml',
                           '/harvest/object/{id}',
                           _redirect_code=u'301 Moved Permanently')

        route_map.connect('/harvest/object/{id}/original', controller=controller,
                          action=u'display_xml_original')

        route_map.connect('/harvest/object/{id}/html', controller=controller,
                          action=u'display_html')
        route_map.connect('/harvest/object/{id}/html/original', controller=controller,
                          action=u'display_html_original')

        # Redirect old URL to a nicer and unversioned one
        route_map.redirect('/api/2/rest/harvestobject/:id/html',
                           '/harvest/object/{id}/html',
                           _redirect_code=u'301 Moved Permanently')

        return route_map

    def after_map(self, route_map):
        '''

        :param route_map: 

        '''
        return route_map

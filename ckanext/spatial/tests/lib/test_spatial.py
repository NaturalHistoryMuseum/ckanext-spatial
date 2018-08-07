#!/usr/bin/env python
# encoding: utf-8

import json
import random
import time

from ckanext.spatial.geoalchemy_common import WKTElement, compare_geometry_fields
from ckanext.spatial.lib import bbox_query, bbox_query_ordered, validate_bbox
from ckanext.spatial.model import PackageExtent
from ckanext.spatial.tests.base import SpatialTestBase
from nose.tools import assert_equal
from shapely.geometry import asShape

from ckan import model
from ckan.lib.munge import munge_title_to_name
from ckan.plugins import toolkit


class TestCompareGeometries(SpatialTestBase):
    ''' '''

    def _get_extent_object(self, geometry):
        '''

        :param geometry: 

        '''
        if isinstance(geometry, basestring):
            geometry = json.loads(geometry)
        shape = asShape(geometry)
        return PackageExtent(package_id=u'xxx',
                             the_geom=WKTElement(shape.wkt, 4326))

    def test_same_points(self):
        ''' '''

        extent1 = self._get_extent_object(self.geojson_examples[u'point'])
        extent2 = self._get_extent_object(self.geojson_examples[u'point'])

        assert compare_geometry_fields(extent1.the_geom, extent2.the_geom)

    def test_different_points(self):
        ''' '''

        extent1 = self._get_extent_object(self.geojson_examples[u'point'])
        extent2 = self._get_extent_object(self.geojson_examples[u'point_2'])

        assert not compare_geometry_fields(extent1.the_geom, extent2.the_geom)


class TestValidateBbox:
    ''' '''
    bbox_dict = {
        u'minx': -4.96,
        u'miny': 55.70,
        u'maxx': -3.78,
        u'maxy': 56.43
        }

    def test_string(self):
        ''' '''
        res = validate_bbox(u'-4.96,55.70,-3.78,56.43')
        assert_equal(res, self.bbox_dict)

    def test_list(self):
        ''' '''
        res = validate_bbox([-4.96, 55.70, -3.78, 56.43])
        assert_equal(res, self.bbox_dict)

    def test_bad(self):
        ''' '''
        res = validate_bbox([-4.96, 55.70, -3.78])
        assert_equal(res, None)

    def test_bad_2(self):
        ''' '''
        res = validate_bbox(u'random')
        assert_equal(res, None)


def bbox_2_geojson(bbox_dict):
    '''

    :param bbox_dict: 

    '''
    return u'{"type":"Polygon","coordinates":[[[%(minx)s, %(miny)s],[%(minx)s, ' \
           u'%(maxy)s], [%(maxx)s, %(maxy)s], [%(maxx)s, %(miny)s], [%(minx)s, ' \
           u'%(miny)s]]]}' % bbox_dict


class SpatialQueryTestBase(SpatialTestBase):
    '''Base class for tests of spatial queries'''
    miny = 0
    maxy = 1

    @classmethod
    def setup_class(cls):
        ''' '''
        SpatialTestBase.setup_class()
        for fixture_x in cls.fixtures_x:
            bbox = cls.x_values_to_bbox(fixture_x)
            bbox_geojson = bbox_2_geojson(bbox)
            cls.create_package(name=munge_title_to_name(str(fixture_x)),
                               title=str(fixture_x),
                               extras=[{
                                   u'key': u'spatial',
                                   u'value': bbox_geojson
                                   }])

    @classmethod
    def create_package(cls, **package_dict):
        '''

        :param **package_dict: 

        '''
        user = toolkit.get_action(u'get_site_user')({
            u'ignore_auth': True
            }, {})
        context = {
            u'user': user[u'name'],
            u'extras_as_string': True,
            u'api_version': 2,
            u'ignore_auth': True,
            }
        package_dict = toolkit.get_action('package_create')(context, package_dict)
        return context.get(u'id')

    @classmethod
    def x_values_to_bbox(cls, x_tuple):
        '''

        :param x_tuple: 

        '''
        return {
            u'minx': x_tuple[0],
            u'maxx': x_tuple[1],
            u'miny': cls.miny,
            u'maxy': cls.maxy
            }


class TestBboxQuery(SpatialQueryTestBase):
    ''' '''
    # x values for the fixtures
    fixtures_x = [(0, 1), (0, 3), (0, 4), (4, 5), (6, 7)]

    def test_query(self):
        ''' '''
        bbox_dict = self.x_values_to_bbox((2, 5))
        package_ids = [res.package_id for res in bbox_query(bbox_dict)]
        package_titles = [model.Package.get(id_).title for id_ in package_ids]
        assert_equal(set(package_titles),
                     set((u'(0, 3)', u'(0, 4)', u'(4, 5)')))


class TestBboxQueryOrdered(SpatialQueryTestBase):
    ''' '''
    # x values for the fixtures
    fixtures_x = [(0, 9), (1, 8), (2, 7), (3, 6), (4, 5),
                  (8, 9)]

    def test_query(self):
        ''' '''
        bbox_dict = self.x_values_to_bbox((2, 7))
        q = bbox_query_ordered(bbox_dict)
        package_ids = [res.package_id for res in q]
        package_titles = [model.Package.get(id_).title for id_ in package_ids]
        # check the right items are returned
        assert_equal(set(package_titles),
                     set((u'(0, 9)', u'(1, 8)', u'(2, 7)', u'(3, 6)', u'(4, 5)')))
        # check the order is good
        assert_equal(package_titles,
                     [u'(2, 7)', u'(1, 8)', u'(3, 6)', u'(0, 9)', u'(4, 5)'])


class TestBboxQueryPerformance(SpatialQueryTestBase):
    ''' '''
    # x values for the fixtures
    fixtures_x = [(random.uniform(0, 3), random.uniform(3, 9)) \
                  for x in xrange(10)]  # increase the number to 1000 say

    def test_query(self):
        ''' '''
        bbox_dict = self.x_values_to_bbox((2, 7))
        t0 = time.time()
        q = bbox_query(bbox_dict)
        t1 = time.time()
        print u'bbox_query took: ', t1 - t0

    def test_query_ordered(self):
        ''' '''
        bbox_dict = self.x_values_to_bbox((2, 7))
        t0 = time.time()
        q = bbox_query_ordered(bbox_dict)
        t1 = time.time()
        print u'bbox_query_ordered took: ', t1 - t0

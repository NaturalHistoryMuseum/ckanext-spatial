#!/usr/bin/env python
# encoding: utf-8

import json
from nose.tools import assert_equals

from ckan.model import Session
from ckan.plugins import toolkit

try:
    import ckan.new_tests.helpers as helpers
    import ckan.new_tests.factories as factories
except ImportError:
    import ckan.tests.helpers as helpers
    import ckan.tests.factories as factories

from ckanext.spatial.model import PackageExtent
from ckanext.spatial.geoalchemy_common import legacy_geoalchemy
from ckanext.spatial.tests.base import SpatialTestBase


class TestSpatialExtra(SpatialTestBase, helpers.FunctionalTestBase):
    ''' '''

    def test_spatial_extra(self):
        ''' '''
        app = self._get_test_app()

        user = factories.User()
        env = {u'REMOTE_USER': user[u'name'].encode(u'ascii')}
        dataset = factories.Dataset(user=user)

        offset = toolkit.url_for(controller=u'package', action=u'edit', id=dataset[u'id'])
        res = app.get(offset, extra_environ=env)

        form = res.forms[1]
        form[u'extras__0__key'] = u'spatial'
        form[u'extras__0__value'] = self.geojson_examples[u'point']

        res = helpers.submit_and_follow(app, form, env, u'save')

        assert u'Error' not in res, res

        package_extent = Session.query(PackageExtent) \
            .filter(PackageExtent.package_id == dataset[u'id']).first()

        geojson = json.loads(self.geojson_examples[u'point'])

        assert_equals(package_extent.package_id, dataset[u'id'])
        if legacy_geoalchemy:
            assert_equals(Session.scalar(package_extent.the_geom.x),
                          geojson[u'coordinates'][0])
            assert_equals(Session.scalar(package_extent.the_geom.y),
                          geojson[u'coordinates'][1])
            assert_equals(Session.scalar(package_extent.the_geom.srid),
                          self.db_srid)
        else:
            from sqlalchemy import func
            assert_equals(
                Session.query(func.ST_X(package_extent.the_geom)).first()[0],
                geojson[u'coordinates'][0])
            assert_equals(
                Session.query(func.ST_Y(package_extent.the_geom)).first()[0],
                geojson[u'coordinates'][1])
            assert_equals(package_extent.the_geom.srid, self.db_srid)

    def test_spatial_extra_edit(self):
        ''' '''
        app = self._get_test_app()

        user = factories.User()
        env = {u'REMOTE_USER': user[u'name'].encode(u'ascii')}
        dataset = factories.Dataset(user=user)

        offset = toolkit.url_for(controller=u'package', action=u'edit', id=dataset[u'id'])
        res = app.get(offset, extra_environ=env)

        form = res.forms[1]
        form[u'extras__0__key'] = u'spatial'
        form[u'extras__0__value'] = self.geojson_examples[u'point']

        res = helpers.submit_and_follow(app, form, env, u'save')

        assert u'Error' not in res, res

        res = app.get(offset, extra_environ=env)

        form = res.forms[1]
        form[u'extras__0__key'] = u'spatial'
        form[u'extras__0__value'] = self.geojson_examples[u'polygon']

        res = helpers.submit_and_follow(app, form, env, u'save')

        assert u'Error' not in res, res

        package_extent = Session.query(PackageExtent) \
            .filter(PackageExtent.package_id == dataset[u'id']).first()

        assert_equals(package_extent.package_id, dataset[u'id'])
        if legacy_geoalchemy:
            assert_equals(
                Session.scalar(package_extent.the_geom.geometry_type),
                u'ST_Polygon')
            assert_equals(
                Session.scalar(package_extent.the_geom.srid),
                self.db_srid)
        else:
            from sqlalchemy import func
            assert_equals(
                Session.query(
                    func.ST_GeometryType(package_extent.the_geom)).first()[0],
                u'ST_Polygon')
            assert_equals(package_extent.the_geom.srid, self.db_srid)

    def test_spatial_extra_bad_json(self):
        ''' '''
        app = self._get_test_app()

        user = factories.User()
        env = {u'REMOTE_USER': user[u'name'].encode(u'ascii')}
        dataset = factories.Dataset(user=user)

        offset = toolkit.url_for(controller=u'package', action=u'edit', id=dataset[u'id'])
        res = app.get(offset, extra_environ=env)

        form = res.forms[1]
        form[u'extras__0__key'] = u'spatial'
        form[u'extras__0__value'] = u'{"Type":Bad Json]'

        res = helpers.webtest_submit(form, extra_environ=env, name=u'save')

        assert u'Error' in res, res
        assert u'Spatial' in res
        assert u'Error decoding JSON object' in res

    def test_spatial_extra_bad_geojson(self):
        ''' '''
        app = self._get_test_app()

        user = factories.User()
        env = {u'REMOTE_USER': user[u'name'].encode(u'ascii')}
        dataset = factories.Dataset(user=user)

        offset = toolkit.url_for(controller=u'package', action=u'edit', id=dataset[u'id'])
        res = app.get(offset, extra_environ=env)

        form = res.forms[1]
        form[u'extras__0__key'] = u'spatial'
        form[u'extras__0__value'] = u'{"Type":"Bad_GeoJSON","a":2}'

        res = helpers.webtest_submit(form, extra_environ=env, name=u'save')

        assert u'Error' in res, res
        assert u'Spatial' in res
        assert u'Error creating geometry' in res

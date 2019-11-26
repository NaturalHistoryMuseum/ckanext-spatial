#!/usr/bin/env python
# encoding: utf-8

from ckanext.spatial.tests.base import SpatialTestBase

from ckan.plugins import toolkit

try:
    import ckan.new_tests.helpers as helpers
    import ckan.new_tests.factories as factories
except ImportError:
    import ckan.tests.helpers as helpers
    import ckan.tests.factories as factories


class TestSpatialWidgets(SpatialTestBase, helpers.FunctionalTestBase):
    ''' '''

    def test_dataset_map(self):
        ''' '''
        app = self._get_test_app()

        user = factories.User()
        dataset = factories.Dataset(
            user=user,
            extras=[{
                u'key': u'spatial',
                u'value': self.geojson_examples[u'point']
                }]
            )
        offset = toolkit.url_for(controller=u'package', action=u'read',
                                 id=dataset[u'id'])
        res = app.get(offset)

        assert u'data-module="dataset-map"' in res
        assert u'dataset_map.js' in res

    def test_spatial_search_widget(self):
        ''' '''

        app = self._get_test_app()

        offset = toolkit.url_for(controller=u'package', action=u'search')
        res = app.get(offset)

        assert u'data-module="spatial-query"' in res
        assert u'spatial_query.js' in res

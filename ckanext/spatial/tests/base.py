#!/usr/bin/env python
# encoding: utf-8

import os
import re
from ckanext.harvest.model import setup as harvest_model_setup
from ckanext.spatial.geoalchemy_common import postgis_version
from ckanext.spatial.model.package_extent import setup as spatial_db_setup
from nose.plugins.skip import SkipTest
from sqlalchemy import Table

from ckan.model import Session, engine_is_sqlite, meta, repo

geojson_examples = {
    u'point': u'{"type":"Point","coordinates":[100.0,0.0]}',
    u'point_2': u'{"type":"Point","coordinates":[20,10]}',
    u'line': u'{"type":"LineString","coordinates":[[100.0,0.0],[101.0,1.0]]}',
    u'polygon': u'{"type":"Polygon","coordinates":[[[100.0,0.0],[101.0,0.0],[101.0,'
                u'1.0],[100.0,1.0],[100.0,0.0]]]}',
    u'polygon_holes': u'{"type":"Polygon","coordinates":[[[100.0,0.0],[101.0,0.0],'
                      u'[101.0,1.0],[100.0,1.0],[100.0,0.0]],[[100.2,0.2],[100.8,0.2],'
                      u'[100.8,0.8],[100.2,0.8],[100.2,0.2]]]}',
    u'multipoint': u'{"type":"MultiPoint","coordinates":[[100.0,0.0],[101.0,1.0]]}',
    u'multiline': u'{"type":"MultiLineString","coordinates":[[[100.0,0.0],[101.0,'
                  u'1.0]],[[102.0,2.0],[103.0,3.0]]]}',
    u'multipolygon': u'{"type":"MultiPolygon","coordinates":[[[[102.0,2.0],[103.0,'
                     u'2.0],[103.0,3.0],[102.0,3.0],[102.0,2.0]]],[[[100.0,0.0],'
                     u'[101.0,0.0],[101.0,1.0],[100.0,1.0],[100.0,0.0]],[[100.2,0.2],'
                     u'[100.8,0.2],[100.8,0.8],[100.2,0.8],[100.2,0.2]]]]}'
    }


def _execute_script(script_path):
    '''

    :param script_path: 

    '''

    conn = Session.connection()
    script = open(script_path, u'r').read()
    for cmd in script.split(u';'):
        cmd = re.sub(r'--(.*)|[\n\t]', u'', cmd)
        if len(cmd):
            conn.execute(cmd)

    Session.commit()


def create_postgis_tables():
    ''' '''
    scripts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                u'scripts')
    if postgis_version()[:1] == u'1':
        _execute_script(os.path.join(scripts_path, u'spatial_ref_sys.sql'))
        _execute_script(os.path.join(scripts_path, u'geometry_columns.sql'))
    else:
        _execute_script(os.path.join(scripts_path, u'spatial_ref_sys.sql'))


class SpatialTestBase(object):
    ''' '''

    db_srid = 4326

    geojson_examples = geojson_examples

    @classmethod
    def setup_class(cls):
        ''' '''
        if engine_is_sqlite():
            raise SkipTest(u'PostGIS is required for this test')

        # This will create the PostGIS tables (geometry_columns and
        # spatial_ref_sys) which were deleted when rebuilding the database
        table = Table(u'spatial_ref_sys', meta.metadata)
        if not table.exists():
            create_postgis_tables()

            # When running the tests with the --reset-db option for some
            # reason the metadata holds a reference to the `package_extent`
            # table after being deleted, causing an InvalidRequestError
            # exception when trying to recreate it further on
            if u'package_extent' in meta.metadata.tables:
                meta.metadata.remove(meta.metadata.tables[u'package_extent'])

        spatial_db_setup()

        # Setup the harvest tables
        harvest_model_setup()

    @classmethod
    def teardown_class(cls):
        ''' '''
        repo.rebuild_db()

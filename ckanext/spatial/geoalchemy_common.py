
#!/usr/bin/env python
# encoding: utf-8

from ckan.plugins import toolkit
from ckan.model import meta, Session

from sqlalchemy import types, Column, Table

if toolkit.check_ckan_version(min_version=u'2.3'):
    # CKAN >= 2.3, use GeoAlchemy2

    from geoalchemy2.elements import WKTElement
    from geoalchemy2 import Geometry
    from sqlalchemy import func
    ST_Transform = func.ST_Transform
    ST_Equals = func.ST_Equals

    legacy_geoalchemy = False
else:
    # CKAN < 2.3, use GeoAlchemy

    from geoalchemy import WKTSpatialElement as WKTElement
    from geoalchemy import functions
    ST_Transform = functions.transform
    ST_Equals = functions.equals

    from geoalchemy import (Geometry, GeometryColumn, GeometryDDL,
                            GeometryExtensionColumn)
    from geoalchemy.postgis import PGComparator

    legacy_geoalchemy = True


def postgis_version():
    ''' '''

    result = Session.execute(u'SELECT postgis_lib_version()')

    return result.scalar()


def setup_spatial_table(package_extent_class, db_srid=None):
    '''

    :param package_extent_class: 
    :param db_srid:  (Default value = None)

    '''

    if legacy_geoalchemy:

        package_extent_table = Table(
            u'package_extent', meta.metadata,
            Column(u'package_id', types.UnicodeText, primary_key=True),
            GeometryExtensionColumn(u'the_geom', Geometry(2, srid=db_srid))
        )

        meta.mapper(
            package_extent_class,
            package_extent_table,
            properties={u'the_geom':
                        GeometryColumn(package_extent_table.c.the_geom,
                                       comparator=PGComparator)}
        )

        GeometryDDL(package_extent_table)
    else:

        # PostGIS 1.5 requires management=True when defining the Geometry
        # field
        management = (postgis_version()[:1] == u'1')

        package_extent_table = Table(
            u'package_extent', meta.metadata,
            Column(u'package_id', types.UnicodeText, primary_key=True),
            Column(u'the_geom', Geometry(u'GEOMETRY', srid=db_srid,
                                        management=management)),
        )

        meta.mapper(package_extent_class, package_extent_table)

    return package_extent_table


def compare_geometry_fields(geom_field1, geom_field2):
    '''

    :param geom_field1: 
    :param geom_field2: 

    '''

    return Session.scalar(ST_Equals(geom_field1, geom_field2))

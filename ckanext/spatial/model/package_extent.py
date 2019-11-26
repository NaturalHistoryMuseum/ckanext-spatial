#!/usr/bin/env python
# encoding: utf-8

from logging import getLogger

from ckanext.spatial.geoalchemy_common import setup_spatial_table
from sqlalchemy import Table

from ckan import model
from ckan.plugins import toolkit

log = getLogger(__name__)

package_extent_table = None

DEFAULT_SRID = 4326


def setup(srid=None):
    '''

    :param srid:  (Default value = None)

    '''

    if package_extent_table is None:
        define_spatial_tables(srid)
        log.debug(u'Spatial tables defined in memory')

    if model.package_table.exists():
        if not Table(u'geometry_columns', model.meta.metadata).exists() or \
                not Table(u'spatial_ref_sys', model.meta.metadata).exists():
            raise Exception(u'The spatial extension is enabled, but PostGIS '
                            u'has not been set up in the database. '
                            u'Please refer to the "Setting up PostGIS" section in the '
                            u'README.')

        if not package_extent_table.exists():
            try:
                package_extent_table.create()
            except Exception, e:
                # Make sure the table does not remain incorrectly created
                # (eg without geom column or constraints)
                if package_extent_table.exists():
                    model.Session.execute(u'DROP TABLE package_extent')
                    model.Session.commit()

                raise e

            log.debug(u'Spatial tables created')
        else:
            log.debug(u'Spatial tables already exist')
            # Future migrations go here

    else:
        log.debug(u'Spatial tables creation deferred')


class PackageExtent(model.domain_object.DomainObject):
    ''' '''

    def __init__(self, package_id=None, the_geom=None):
        self.package_id = package_id
        self.the_geom = the_geom


def define_spatial_tables(db_srid=None):
    '''

    :param db_srid:  (Default value = None)

    '''

    global package_extent_table

    if not db_srid:
        db_srid = int(toolkit.config.get(u'ckan.spatial.srid', DEFAULT_SRID))
    else:
        db_srid = int(db_srid)

    package_extent_table = setup_spatial_table(PackageExtent, db_srid)

#!/usr/bin/env python
# encoding: utf-8

import logging
from string import Template

from ckanext.spatial.geoalchemy_common import (ST_Transform, WKTElement,
                                               compare_geometry_fields)
from ckanext.spatial.model import PackageExtent
from shapely.geometry import asShape

from ckan.model import Package, Session
from ckan.plugins import toolkit

log = logging.getLogger(__name__)


def get_srid(crs):
    '''Returns the SRID for the provided CRS definition
        The CRS can be defined in the following formats
        - urn:ogc:def:crs:EPSG::4326
        - EPSG:4326
        - 4326

    :param crs: 

    '''

    if u':' in crs:
        crs = crs.split(u':')
        srid = crs[len(crs) - 1]
    else:
        srid = crs

    return int(srid)


def save_package_extent(package_id, geometry=None, srid=None):
    '''Adds, updates or deletes the package extent geometry.
    
       package_id: Package unique identifier
       geometry: a Python object implementing the Python Geo Interface
                (i.e a loaded GeoJSON object)
       srid: The spatial reference in which the geometry is provided.
             If None, it defaults to the DB srid.
    
       Will throw ValueError if the geometry object does not provide a geo interface.
    
       The responsibility for calling model.Session.commit() is left to the
       caller.

    :param package_id: 
    :param geometry:  (Default value = None)
    :param srid:  (Default value = None)

    '''
    db_srid = int(toolkit.config.get(u'ckan.spatial.srid', u'4326'))

    existing_package_extent = Session.query(PackageExtent).filter(
        PackageExtent.package_id == package_id).first()

    if geometry:
        shape = asShape(geometry)

        if not srid:
            srid = db_srid

        package_extent = PackageExtent(package_id=package_id,
                                       the_geom=WKTElement(shape.wkt, srid))

    # Check if extent exists
    if existing_package_extent:

        # If extent exists but we received no geometry, we'll delete the existing one
        if not geometry:
            existing_package_extent.delete()
            log.debug(u'Deleted extent for package %s' % package_id)
        else:
            # Check if extent changed
            if not compare_geometry_fields(package_extent.the_geom,
                                           existing_package_extent.the_geom):
                # Update extent
                existing_package_extent.the_geom = package_extent.the_geom
                existing_package_extent.save()
                log.debug(u'Updated extent for package %s' % package_id)
            else:
                log.debug(u'Extent for package %s unchanged' % package_id)
    elif geometry:
        # Insert extent
        Session.add(package_extent)
        log.debug(u'Created new extent for package %s' % package_id)


def validate_bbox(bbox_values):
    '''Ensures a bbox is expressed in a standard dict.
    
    bbox_values may be:
           a string: "-4.96,55.70,-3.78,56.43"
           or a list [-4.96, 55.70, -3.78, 56.43]
           or a list of strings ["-4.96", "55.70", "-3.78", "56.43"]
    and returns a dict:
           {'minx': -4.96,
            'miny': 55.70,
            'maxx': -3.78,
            'maxy': 56.43}
    
    Any problems and it returns None.

    :param bbox_values: 

    '''

    if isinstance(bbox_values, basestring):
        bbox_values = bbox_values.split(u',')

    if len(bbox_values) is not 4:
        return None

    try:
        bbox = {}
        bbox[u'minx'] = float(bbox_values[0])
        bbox[u'miny'] = float(bbox_values[1])
        bbox[u'maxx'] = float(bbox_values[2])
        bbox[u'maxy'] = float(bbox_values[3])
    except ValueError, e:
        return None

    return bbox


def _bbox_2_wkt(bbox, srid):
    '''Given a bbox dictionary, return a WKTSpatialElement, transformed
    into the database\'s CRS if necessary.
    
    returns e.g. WKTSpatialElement("POLYGON ((2 0, 2 1, 7 1, 7 0, 2 0))", 4326)

    :param bbox: 
    :param srid: 

    '''
    db_srid = int(toolkit.config.get(u'ckan.spatial.srid', u'4326'))

    bbox_template = Template(
        u'POLYGON (($minx $miny, $minx $maxy, $maxx $maxy, $maxx $miny, $minx $miny))')

    wkt = bbox_template.substitute(minx=bbox[u'minx'],
                                   miny=bbox[u'miny'],
                                   maxx=bbox[u'maxx'],
                                   maxy=bbox[u'maxy'])

    if srid and srid != db_srid:
        # Input geometry needs to be transformed to the one used on the database
        input_geometry = ST_Transform(WKTElement(wkt, srid), db_srid)
    else:
        input_geometry = WKTElement(wkt, db_srid)
    return input_geometry


def bbox_query(bbox, srid=None):
    '''Performs a spatial query of a bounding box.
    
    bbox - bounding box dict
    
    Returns a query object of PackageExtents, which each reference a package
    by ID.

    :param bbox: 
    :param srid:  (Default value = None)

    '''

    input_geometry = _bbox_2_wkt(bbox, srid)

    extents = Session.query(PackageExtent) \
        .filter(PackageExtent.package_id == Package.id) \
        .filter(PackageExtent.the_geom.intersects(input_geometry)) \
        .filter(Package.state == u'active')
    return extents


def bbox_query_ordered(bbox, srid=None):
    '''Performs a spatial query of a bounding box. Returns packages in order
    of how similar the data\'s bounding box is to the search box (best first).
    
    bbox - bounding box dict
    
    Returns a query object of PackageExtents, which each reference a package
    by ID.

    :param bbox: 
    :param srid:  (Default value = None)

    '''

    input_geometry = _bbox_2_wkt(bbox, srid)

    params = {
        u'query_bbox': str(input_geometry),
        u'query_srid': input_geometry.srid
        }

    # First get the area of the query box
    sql = u'SELECT ST_Area(ST_GeomFromText(:query_bbox, :query_srid));'
    params[u'search_area'] = Session.execute(sql, params).fetchone()[0]

    # Uses spatial ranking method from "USGS - 2006-1279" (Lanfear)
    sql = u'''SELECT ST_AsBinary(package_extent.the_geom) AS package_extent_the_geom,
                    POWER(ST_Area(ST_Intersection(package_extent.the_geom, 
                    ST_GeomFromText(:query_bbox, :query_srid))),2)/ST_Area(
                    package_extent.the_geom)/:search_area as spatial_ranking,
                    package_extent.package_id AS package_id
             FROM package_extent, package
             WHERE package_extent.package_id = package.id
                AND ST_Intersects(package_extent.the_geom, ST_GeomFromText(
                :query_bbox, :query_srid))
                AND package.state = 'active'
             ORDER BY spatial_ranking desc'''
    extents = Session.execute(sql, params).fetchall()
    log.debug(u'Spatial results: %r',
              [(u'%.2f' % extent.spatial_ranking, extent.package_id) for extent in
               extents[:20]])
    return extents

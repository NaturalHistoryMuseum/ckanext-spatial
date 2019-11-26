#!/usr/bin/env python
# encoding: utf-8

import logging

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from pkg_resources import resource_stream
from lxml import etree

from ckan.controllers.api import ApiController as BaseApiController
from ckan.model import Session

from ckan.plugins import toolkit

from ckanext.harvest.model import HarvestObject, HarvestObjectExtra
from ckanext.spatial.lib import get_srid, validate_bbox, bbox_query

log = logging.getLogger(__name__)


class ApiController(BaseApiController):
    ''' '''

    def spatial_query(self):
        ''' '''

        error_400_msg = \
            u'Please provide a suitable bbox parameter [minx,miny,maxx,maxy]'

        if not u'bbox' in toolkit.request.params:
            toolkit.abort(400, error_400_msg)

        bbox = validate_bbox(toolkit.request.params[u'bbox'])

        if not bbox:
            toolkit.abort(400, error_400_msg)

        srid = get_srid(toolkit.request.params.get(
            u'crs')) if u'crs' in toolkit.request.params else None

        extents = bbox_query(bbox, srid)

        format = toolkit.request.params.get(u'format', u'')

        return self._output_results(extents, format)

    def _output_results(self, extents, format=None):
        '''

        :param extents: 
        :param format:  (Default value = None)

        '''

        ids = [extent.package_id for extent in extents]
        output = dict(count=len(ids), results=ids)

        return self._finish_ok(output)


class HarvestMetadataApiController(BaseApiController):
    ''' '''

    def _get_content(self, id):
        '''

        :param id: 

        '''

        obj = Session.query(HarvestObject) \
            .filter(HarvestObject.id == id).first()
        if obj:
            return obj.content
        else:
            return None

    def _get_original_content(self, id):
        '''

        :param id: 

        '''
        extra = Session.query(HarvestObjectExtra).join(HarvestObject) \
            .filter(HarvestObject.id == id) \
            .filter(
            HarvestObjectExtra.key == u'original_document'
            ).first()
        if extra:
            return extra.value
        else:
            return None

    def _transform_to_html(self, content, xslt_package=None, xslt_path=None):
        '''

        :param content: 
        :param xslt_package:  (Default value = None)
        :param xslt_path:  (Default value = None)

        '''

        xslt_package = xslt_package or __name__
        xslt_path = xslt_path or \
                    u'../templates/ckanext/spatial/gemini2-html-stylesheet.xsl'

        # optimise -- read transform only once and compile rather
        # than at each request
        with resource_stream(xslt_package, xslt_path) as style:
            style_xml = etree.parse(style)
            transformer = etree.XSLT(style_xml)

        xml = etree.parse(StringIO(content.encode(u'utf-8')))
        html = transformer(xml)

        toolkit.response.headers[u'Content-Type'] = u'text/html; charset=utf-8'
        toolkit.response.headers[u'Content-Length'] = len(content)

        result = etree.tostring(html, pretty_print=True)

        return result

    def _get_xslt(self, original=False):
        '''

        :param original:  (Default value = False)

        '''

        if original:
            config_option = \
                u'ckanext.spatial.harvest.xslt_html_content_original'
        else:
            config_option = u'ckanext.spatial.harvest.xslt_html_content'

        xslt_package = None
        xslt_path = None
        xslt = toolkit.config.get(config_option, None)
        if xslt:
            if u':' in xslt:
                xslt = xslt.split(u':')
                xslt_package = xslt[0]
                xslt_path = xslt[1]
            else:
                log.error(
                    u'XSLT should be defined in the form <package>:<path>' +
                    u', eg ckanext.myext:templates/my.xslt')

        return xslt_package, xslt_path

    def display_xml_original(self, id):
        '''

        :param id: 

        '''
        content = self._get_original_content(id)

        if not content:
            toolkit.abort(404)

        toolkit.response.headers[u'Content-Type'] = u'application/xml; charset=utf-8'
        toolkit.response.headers[u'Content-Length'] = len(content)

        if not u'<?xml' in content.split(u'\n')[0]:
            content = u'<?xml version="1.0" encoding="UTF-8"?>\n' + content
        return content.encode(u'utf-8')

    def display_html(self, id):
        '''

        :param id: 

        '''
        content = self._get_content(id)

        if not content:
            toolkit.abort(404)

        xslt_package, xslt_path = self._get_xslt()
        return self._transform_to_html(content, xslt_package, xslt_path)

    def display_html_original(self, id):
        '''

        :param id: 

        '''
        content = self._get_original_content(id)

        if content is None:
            toolkit.abort(404)

        xslt_package, xslt_path = self._get_xslt(original=True)
        return self._transform_to_html(content, xslt_package, xslt_path)

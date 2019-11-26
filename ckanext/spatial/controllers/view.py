#!/usr/bin/env python
# encoding: utf-8

import urllib2

from ckan.model import Package
from ckan.plugins import toolkit


class ViewController(toolkit.BaseController):
    ''' '''

    def wms_preview(self, id):
        '''

        :param id: 

        '''
        # check if package exists
        toolkit.c.pkg = Package.get(id)
        if toolkit.c.pkg is None:
            toolkit.abort(404, u'Dataset not found')

        for res in toolkit.c.pkg.resources:
            if res.format.lower() == u'wms':
                toolkit.c.wms_url = res.url \
                    if u'?' not in res.url else res.url.split(u'?')[0]
                break
        if not toolkit.c.wms_url:
            toolkit.abort(400, u'This dataset does not have a WMS resource')

        return toolkit.render(u'ckanext/spatial/wms_preview.html')

    def proxy(self):
        ''' '''
        if u'url' not in toolkit.request.params:
            toolkit.abort(400)
        try:
            server_response = urllib2.urlopen(toolkit.request.params[u'url'])
            headers = server_response.info()
            if headers.get(u'Content-Type'):
                toolkit.response.content_type = headers.get(u'Content-Type')
            return server_response.read()
        except urllib2.HTTPError as e:
            toolkit.response.status_int = e.getcode()
            return

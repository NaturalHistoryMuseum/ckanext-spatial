#!/usr/bin/env python
# encoding: utf-8

from ckan.plugins import SingletonPlugin, implements, interfaces, toolkit


class TestSpatialPlugin(SingletonPlugin):
    ''' '''

    implements(interfaces.IConfigurer, inherit=True)

    def update_config(self, config):
        '''

        :param config: 

        '''
        toolkit.add_template_directory(config, u'templates')

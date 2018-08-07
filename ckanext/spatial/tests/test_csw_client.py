#!/usr/bin/env python
# encoding: utf-8

import os
from nose.plugins.skip import SkipTest

from ckan.model import engine_is_sqlite
from ckan.plugins import toolkit


class CkanServerCase:
    ''' '''

    @staticmethod
    def _system(cmd):
        '''

        :param cmd: 

        '''
        import commands
        (status, output) = commands.getstatusoutput(cmd)
        if status:
            raise Exception, u"Couldn't execute cmd: %s: %s" % (cmd, output)

    @classmethod
    def _paster(cls, cmd, config_path_rel):
        '''

        :param cmd: 
        :param config_path_rel: 

        '''
        config_path = os.path.join(toolkit.config[u'here'], config_path_rel)
        cls._system(u'paster --plugin ckan %s --config=%s' % (cmd, config_path))

    @staticmethod
    def _start_ckan_server(config_file=None):
        '''

        :param config_file:  (Default value = None)

        '''
        if not config_file:
            config_file = toolkit.config[u'__file__']
        config_path = config_file
        import subprocess
        process = subprocess.Popen([u'paster', u'serve', config_path])
        return process

    @staticmethod
    def _wait_for_url(url=u'http://127.0.0.1:5000/', timeout=15):
        '''

        :param url:  (Default value = u'http://127.0.0.1:5000/')
        :param timeout:  (Default value = 15)

        '''
        for i in range(int(timeout) * 100):
            import urllib2
            import time
            try:
                response = urllib2.urlopen(url)
            except urllib2.URLError:
                time.sleep(0.01)
            else:
                break

    @staticmethod
    def _stop_ckan_server(process):
        '''

        :param process: 

        '''
        pid = process.pid
        pid = int(pid)
        if os.system(u'kill -9 %d' % pid):
            raise Exception, u"Can't kill foreign CKAN instance (pid: %d)." % pid


class CkanProcess(CkanServerCase):
    ''' '''

    @classmethod
    def setup_class(cls):
        ''' '''
        if engine_is_sqlite():
            raise SkipTest(u'Non-memory database needed for this test')

        cls.pid = cls._start_ckan_server()
        ## Don't need to init database, since it is same database as this process uses
        cls._wait_for_url()

    @classmethod
    def teardown_class(cls):
        ''' '''
        cls._stop_ckan_server(cls.pid)

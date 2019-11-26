#!/usr/bin/env python
# encoding: utf-8

import logging
import sys

from bin import ckan_pycsw
from paste import script
log = logging.getLogger(__name__)


class Pycsw(script.command.Command):
    '''Manages the CKAN-pycsw integration
    
    ckan-pycsw setup [-p]
        Setups the necessary pycsw table on the db.
    
    ckan-pycsw set_keywords [-p] [-u]
        Sets pycsw server metadata keywords from CKAN site tag list.
    
    ckan-pycsw load [-p] [-u]
        Loads CKAN datasets as records into the pycsw db.
    
    ckan-pycsw clear [-p]
        Removes all records from the pycsw table.
    
    All commands require the pycsw configuration file. By default it will try
    to find a file called 'default.cfg' in the same directory, but you'll
    probably need to provide the actual location with the -p option.
    
    paster ckan-pycsw setup -p /etc/ckan/default/pycsw.cfg
    
    The load command requires a CKAN URL from where the datasets will be pulled.
    By default it is set to 'http://localhost', but you can define it with the -u
    option:
    
    paster ckan-pycsw load -p /etc/ckan/default/pycsw.cfg -u http://ckan.instance.org


    '''

    parser = script.command.Command.standard_parser(verbose=True)
    parser.add_option(u'-p', u'--pycsw-config', dest=u'pycsw_config',
                      default=u'default.cfg', help=u'pycsw config file to use.')
    parser.add_option(u'-u', u'--ckan-url', dest=u'ckan_url',
                      default=u'http://localhost',
                      help=u'CKAN instance to import the datasets from.')

    summary = __doc__.split(u'\n')[0]
    usage = __doc__
    max_args = 2
    min_args = 0

    def command(self):
        ''' '''
        if len(self.args) == 0:
            self.parser.print_usage()
            sys.exit(1)

        config = ckan_pycsw._load_config(self.options.pycsw_config)
        cmd = self.args[0]
        if cmd == u'setup':
            ckan_pycsw.setup_db(config)
        elif cmd in [u'load', u'set_keywords']:
            ckan_url = self.options.ckan_url.rstrip('/') + '/'
            if cmd == u'load':
                ckan_pycsw.load(config, ckan_url)
            else:
                ckan_pycsw.set_keywords(self.options.pycsw_config, config, ckan_url)
        elif cmd == u'clear':
            ckan_pycsw.clear(config)
        else:
            print u'Command %s not recognized' % cmd

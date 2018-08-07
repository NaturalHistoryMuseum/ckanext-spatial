#!/usr/bin/env python
# encoding: utf-8

import logging
import sys
from pprint import pprint

import os
from lxml import etree

from ckan.plugins import toolkit

log = logging.getLogger(__name__)


class Validation(toolkit.CkanCommand):
    '''Validation commands
    
    Usage:
        validation report [package-name]
            Performs validation on the harvested metadata, either for all
            packages or the one specified.
    
        validation report-csv <filename>.csv
            Performs validation on all the harvested metadata in the db and
            writes a report in CSV format to the given filepath.
    
        validation file <filename>.xml
            Performs validation on the given metadata file.


    '''
    summary = __doc__.split(u'\n')[0]
    usage = __doc__
    max_args = 3
    min_args = 0

    def command(self):
        ''' '''
        if not self.args or self.args[0] in [u'--help', u'-h', u'help']:
            print self.usage
            sys.exit(1)

        self._load_config()

        cmd = self.args[0]
        if cmd == u'report':
            self.report()
        elif cmd == u'report-csv':
            self.report_csv()
        elif cmd == u'file':
            self.validate_file()
        else:
            print u'Command %s not recognized' % cmd

    def report(self):
        ''' '''
        from ckan import model
        from ckanext.spatial.lib.reports import validation_report

        if len(self.args) >= 2:
            package_ref = unicode(self.args[1])
            pkg = model.Package.get(package_ref)
            if not pkg:
                print u'Package ref "%s" not recognised' % package_ref
                sys.exit(1)
        else:
            pkg = None

        report = validation_report(package_id=pkg.id)
        for row in report.get_rows_html_formatted():
            print
            for i, col_name in enumerate(report.column_names):
                print u'  %s: %s' % (col_name, row[i])

    def validate_file(self):
        ''' '''
        from ckanext.spatial.harvesters import SpatialHarvester
        from ckanext.spatial.model import ISODocument

        if len(self.args) > 2:
            print u'Too many parameters %i' % len(self.args)
            sys.exit(1)
        if len(self.args) < 2:
            print u'Not enough parameters %i' % len(self.args)
            sys.exit(1)
        metadata_filepath = self.args[1]
        if not os.path.exists(metadata_filepath):
            print u'Filepath %s not found' % metadata_filepath
            sys.exit(1)
        with open(metadata_filepath, u'rb') as f:
            metadata_xml = f.read()

        validators = SpatialHarvester()._get_validator()
        print u'Validators: %r' % validators.profiles
        try:
            xml_string = metadata_xml.encode(u'utf-8')
        except UnicodeDecodeError, e:
            print u'ERROR: Unicode Error reading file \'%s\': %s' % \
                  (metadata_filepath, e)
            sys.exit(1)
            # import pdb; pdb.set_trace()
        xml = etree.fromstring(xml_string)

        # XML validation
        valid, errors = validators.is_valid(xml)

        # CKAN read of values
        if valid:
            try:
                iso_document = ISODocument(xml_string)
                iso_values = iso_document.read_values()
            except Exception, e:
                valid = False
                errors.append(u'CKAN exception reading values from ISODocument: %s' % e)

        print u'***************'
        print u'Summary'
        print u'***************'
        print u'File: \'%s\'' % metadata_filepath
        print u'Valid: %s' % valid
        if not valid:
            print u'Errors:'
            print pprint(errors)
        print u'***************'

    def report_csv(self):
        ''' '''
        from ckanext.spatial.lib.reports import validation_report
        if len(self.args) != 2:
            print u'Wrong number of arguments'
            sys.exit(1)
        csv_filepath = self.args[1]
        report = validation_report()
        with open(csv_filepath, u'wb') as f:
            f.write(report.get_csv())

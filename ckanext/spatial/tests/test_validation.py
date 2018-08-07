#!/usr/bin/env python
# encoding: utf-8

import os
from ckanext.spatial import validation
from lxml import etree
from nose.tools import assert_equal, assert_in


class TestValidation:
    ''' '''

    def _get_file_path(self, file_name):
        '''

        :param file_name: 

        '''
        return os.path.join(os.path.dirname(__file__), u'xml', file_name)

    def get_validation_errors(self, validator, validation_test_filename):
        '''

        :param validator: 
        :param validation_test_filename: 

        '''
        validation_test_filepath = self._get_file_path(validation_test_filename)
        xml = etree.parse(validation_test_filepath)
        is_valid, errors = validator.is_valid(xml)

        return u';'.join([e[0] for e in errors])

    def test_iso19139_failure(self):
        ''' '''
        errors = self.get_validation_errors(validation.ISO19139Schema,
                                            u'iso19139/dataset-invalid.xml')

        assert len(errors) > 0
        assert_in(u'Dataset schema (gmx.xsd)', errors)
        assert_in(
            u'{http://www.isotc211.org/2005/gmd}nosuchelement\': This element is not '
            u'expected.',
            errors)

    def test_iso19139_pass(self):
        ''' '''
        errors = self.get_validation_errors(validation.ISO19139Schema,
                                            u'iso19139/dataset.xml')
        assert_equal(errors, u'')

    # Gemini2.1 tests are basically the same as those in test_harvest.py but
    # a few little differences make it worth not removing them in
    # test_harvest

    def test_01_dataset_fail_iso19139_schema(self):
        ''' '''
        errors = self.get_validation_errors(validation.ISO19139EdenSchema,
                                            u'gemini2.1/validation/01_Dataset_Invalid_'
                                            u'XSD_No_Such_Element.xml')
        assert len(errors) > 0
        assert_in(u'(gmx.xsd)', errors)
        assert_in(
            u'\'{http://www.isotc211.org/2005/gmd}nosuchelement\': This element is not '
            u'expected.',
            errors)

    def test_02_dataset_fail_constraints_schematron(self):
        ''' '''
        errors = self.get_validation_errors(validation.ConstraintsSchematron14,
                                            u'gemini2.1/validation/02_Dataset_Invalid_'
                                            u'19139_Missing_Data_Format.xml')
        assert len(errors) > 0
        assert_in(
            u'MD_Distribution / MD_Format: count(distributionFormat + '
            u'distributorFormat) > 0',
            errors)

    def test_03_dataset_fail_gemini_schematron(self):
        ''' '''
        errors = self.get_validation_errors(validation.Gemini2Schematron,
                                            u'gemini2.1/validation/03_Dataset_Invalid_'
                                            u'GEMINI_Missing_Keyword.xml')
        assert len(errors) > 0
        assert_in(u'Descriptive keywords are mandatory', errors)

    def assert_passes_all_gemini2_1_validation(self, xml_filepath):
        '''

        :param xml_filepath: 

        '''
        errs = self.get_validation_errors(validation.ISO19139EdenSchema,
                                          xml_filepath)
        assert not errs, u'ISO19139EdenSchema: ' + errs
        errs = self.get_validation_errors(validation.ConstraintsSchematron14,
                                          xml_filepath)
        assert not errs, u'ConstraintsSchematron14: ' + errs
        errs = self.get_validation_errors(validation.Gemini2Schematron,
                                          xml_filepath)
        assert not errs, u'Gemini2Schematron: ' + errs

    def test_04_dataset_valid(self):
        ''' '''
        self.assert_passes_all_gemini2_1_validation(
            u'gemini2.1/validation/04_Dataset_Valid.xml')

    def test_05_series_fail_iso19139_schema(self):
        ''' '''
        errors = self.get_validation_errors(validation.ISO19139EdenSchema,
                                            u'gemini2.1/validation/05_Series_Invalid_'
                                            u'XSD_No_Such_Element.xml')
        assert len(errors) > 0
        assert_in(u'(gmx.xsd)', errors)
        assert_in(
            u'\'{http://www.isotc211.org/2005/gmd}nosuchelement\': This element is not '
            u'expected.',
            errors)

    def test_06_series_fail_constraints_schematron(self):
        ''' '''
        errors = self.get_validation_errors(validation.ConstraintsSchematron14,
                                            u'gemini2.1/validation/06_Series_Invalid_'
                                            u'19139_Missing_Data_Format.xml')
        assert len(errors) > 0
        assert_in(
            u'MD_Distribution / MD_Format: count(distributionFormat + '
            u'distributorFormat) > 0',
            errors)

    def test_07_series_fail_gemini_schematron(self):
        ''' '''
        errors = self.get_validation_errors(validation.Gemini2Schematron,
                                            u'gemini2.1/validation/07_Series_Invalid_'
                                            u'GEMINI_Missing_Keyword.xml')
        assert len(errors) > 0
        assert_in(u'Descriptive keywords are mandatory', errors)

    def test_08_series_valid(self):
        ''' '''
        self.assert_passes_all_gemini2_1_validation(
            u'gemini2.1/validation/08_Series_Valid.xml')

    def test_09_service_fail_iso19139_schema(self):
        ''' '''
        errors = self.get_validation_errors(validation.ISO19139EdenSchema,
                                            u'gemini2.1/validation/09_Service_Invalid_'
                                            u'No_Such_Element.xml')
        assert len(errors) > 0
        assert_in(u'(gmx.xsd & srv.xsd)', errors)
        assert_in(
            u'\'{http://www.isotc211.org/2005/gmd}nosuchelement\': This element is not '
            u'expected.',
            errors)

    def test_10_service_fail_constraints_schematron(self):
        ''' '''
        errors = self.get_validation_errors(validation.ConstraintsSchematron14,
                                            u'gemini2.1/validation/10_Service_Invalid_'
                                            u'19139_Level_Description.xml')
        assert len(errors) > 0
        assert_in(
            u"DQ_Scope: 'levelDescription' is mandatory if 'level' notEqual 'dataset' "
            u"or 'series'.",
            errors)

    def test_11_service_fail_gemini_schematron(self):
        ''' '''
        errors = self.get_validation_errors(validation.Gemini2Schematron,
                                            u'gemini2.1/validation/11_Service_Invalid_'
                                            u'GEMINI_Service_Type.xml')
        assert len(errors) > 0
        assert_in(
            u"Service type shall be one of 'discovery', 'view', 'download', "
            u"'transformation', 'invoke' or 'other' following INSPIRE generic names.",
            errors)

    def test_12_service_valid(self):
        ''' '''
        self.assert_passes_all_gemini2_1_validation(
            u'gemini2.1/validation/12_Service_Valid.xml')

    def test_13_dataset_fail_iso19139_schema_2(self):
        ''' '''
        # This test Dataset has srv tags and only Service metadata should.
        errors = self.get_validation_errors(validation.ISO19139EdenSchema,
                                            u'gemini2.1/validation/13_Dataset_Invalid_'
                                            u'Element_srv.xml')
        assert len(errors) > 0
        assert_in(u'(gmx.xsd)', errors)
        assert_in(
            u'Element \'{http://www.isotc211.org/2005/srv}SV_ServiceIdentification\': '
            u'This element is not expected.',
            errors)

    def test_schematron_error_extraction(self):
        validation_error_xml = u'''
<root xmlns:svrl="http://purl.oclc.org/dsdl/svrl">
  <svrl:failed-assert test="srv:serviceType/*[1] = 'discovery' or srv:serviceType/*[1] 
  = 'view' or srv:serviceType/*[1] = 'download' or srv:serviceType/*[1] = 
  'transformation' or srv:serviceType/*[1] = 'invoke' or srv:serviceType/*[1] = 
  'other'" location="/*[local-name()='MD_Metadata' and namespace-uri(
  )='http://www.isotc211.org/2005/gmd']/*[local-name()='identificationInfo' and 
  namespace-uri()='http://www.isotc211.org/2005/gmd']/*[local-name(
  )='SV_ServiceIdentification' and namespace-uri()='http://www.isotc211.org/2005/srv']">
    <svrl:text>
        Service type shall be one of 'discovery', 'view', 'download', 
        'transformation', 'invoke' or 'other' following INSPIRE generic names.
      </svrl:text>
  </svrl:failed-assert>
</root>
'''
        failure_xml = etree.fromstring(validation_error_xml)
        fail_element = failure_xml.getchildren()[0]
        details = validation.SchematronValidator.extract_error_details(fail_element)
        if isinstance(details, tuple):
            details = details[1]
        assert_in(u"srv:serviceType/*[1] = 'discovery'", details)
        assert_in(u"/*[local-name()='MD_Metadata'", details)
        assert_in(u"Service type shall be one of 'discovery'", details)


def test_error_line_numbers(self):
    ''' '''
    file_path = self._get_file_path(u'iso19139/dataset-invalid.xml')
    xml = etree.parse(file_path)
    is_valid, profile, errors = validation.Validators(profiles=[u'iso19139']).is_valid(
        xml)
    assert not is_valid
    assert len(errors) == 2

    message, line = errors[1]
    assert u'This element is not expected' in message
    assert line == 3

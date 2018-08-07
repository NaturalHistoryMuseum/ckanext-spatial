#!/usr/bin/env python
# encoding: utf-8

import logging

from lxml import etree
log = logging.getLogger(__name__)


class MappedXmlObject(object):
    ''' '''
    elements = []


class MappedXmlDocument(MappedXmlObject):
    ''' '''

    def __init__(self, xml_str=None, xml_tree=None):
        assert (
                    xml_str or xml_tree is not None), u'Must provide some XML in one ' \
                                                      u'format or another'
        self.xml_str = xml_str
        self.xml_tree = xml_tree

    def read_values(self):
        '''For all of the elements listed, finds the values of them in the
        XML and returns them.


        '''
        values = {}
        tree = self.get_xml_tree()
        for element in self.elements:
            values[element.name] = element.read_value(tree)
        self.infer_values(values)
        return values

    def read_value(self, name):
        '''For the given element name, find the value in the XML and return
        it.

        :param name: 

        '''
        tree = self.get_xml_tree()
        for element in self.elements:
            if element.name == name:
                return element.read_value(tree)
        raise KeyError

    def get_xml_tree(self):
        ''' '''
        if self.xml_tree is None:
            parser = etree.XMLParser(remove_blank_text=True)
            if type(self.xml_str) == unicode:
                xml_str = self.xml_str.encode(u'utf8')
            else:
                xml_str = self.xml_str
            self.xml_tree = etree.fromstring(xml_str, parser=parser)
        return self.xml_tree

    def infer_values(self, values):
        '''

        :param values: 

        '''
        pass


class MappedXmlElement(MappedXmlObject):
    ''' '''
    namespaces = {}

    def __init__(self, name, search_paths=[], multiplicity=u'*', elements=[]):
        self.name = name
        self.search_paths = search_paths
        self.multiplicity = multiplicity
        self.elements = elements or self.elements

    def read_value(self, tree):
        '''

        :param tree: 

        '''
        values = []
        for xpath in self.get_search_paths():
            elements = self.get_elements(tree, xpath)
            values = self.get_values(elements)
            if values:
                break
        return self.fix_multiplicity(values)

    def get_search_paths(self):
        ''' '''
        if type(self.search_paths) != type([]):
            search_paths = [self.search_paths]
        else:
            search_paths = self.search_paths
        return search_paths

    def get_elements(self, tree, xpath):
        '''

        :param tree: 
        :param xpath: 

        '''
        return tree.xpath(xpath, namespaces=self.namespaces)

    def get_values(self, elements):
        '''

        :param elements: 

        '''
        values = []
        if len(elements) == 0:
            pass
        else:
            for element in elements:
                value = self.get_value(element)
                values.append(value)
        return values

    def get_value(self, element):
        '''

        :param element: 

        '''
        if self.elements:
            value = {}
            for child in self.elements:
                value[child.name] = child.read_value(element)
            return value
        elif type(element) == etree._ElementStringResult:
            value = str(element)
        elif type(element) == etree._ElementUnicodeResult:
            value = unicode(element)
        else:
            value = self.element_tostring(element)
        return value

    def element_tostring(self, element):
        '''

        :param element: 

        '''
        return etree.tostring(element, pretty_print=False)

    def fix_multiplicity(self, values):
        '''When a field contains multiple values, yet the spec says
        it should contain only one, then return just the first value,
        rather than a list.
        
        In the ISO19115 specification, multiplicity relates to:
        * 'Association Cardinality'
        * 'Obligation/Condition' & 'Maximum Occurence'

        :param values: 

        '''
        if self.multiplicity == u'0':
            # 0 = None
            if values:
                log.warn(
                    u"Values found for element '%s' when multiplicity should be 0: %s",
                    self.name, values)
            return u''
        elif self.multiplicity == u'1':
            # 1 = Mandatory, maximum 1 = Exactly one
            if not values:
                log.warn(u"Value not found for element '%s'" % self.name)
                return u''
            return values[0]
        elif self.multiplicity == u'*':
            # * = 0..* = zero or more
            return values
        elif self.multiplicity == u'0..1':
            # 0..1 = Mandatory, maximum 1 = optional (zero or one)
            if values:
                return values[0]
            else:
                return u''
        elif self.multiplicity == u'1..*':
            # 1..* = one or more
            return values
        else:
            log.warning(u'Multiplicity not specified for element: %s',
                        self.name)
            return values


class ISOElement(MappedXmlElement):
    ''' '''

    namespaces = {
        u'gts': u'http://www.isotc211.org/2005/gts',
        u'gml': u'http://www.opengis.net/gml',
        u'gml32': u'http://www.opengis.net/gml/3.2',
        u'gmx': u'http://www.isotc211.org/2005/gmx',
        u'gsr': u'http://www.isotc211.org/2005/gsr',
        u'gss': u'http://www.isotc211.org/2005/gss',
        u'gco': u'http://www.isotc211.org/2005/gco',
        u'gmd': u'http://www.isotc211.org/2005/gmd',
        u'srv': u'http://www.isotc211.org/2005/srv',
        u'xlink': u'http://www.w3.org/1999/xlink',
        u'xsi': u'http://www.w3.org/2001/XMLSchema-instance',
        }


class ISOResourceLocator(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'url',
            search_paths=[
                u'gmd:linkage/gmd:URL/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'function',
            search_paths=[
                u'gmd:function/gmd:CI_OnLineFunctionCode/@codeListValue',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'name',
            search_paths=[
                u'gmd:name/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'description',
            search_paths=[
                u'gmd:description/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'protocol',
            search_paths=[
                u'gmd:protocol/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ]


class ISOResponsibleParty(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'individual-name',
            search_paths=[
                u'gmd:individualName/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'organisation-name',
            search_paths=[
                u'gmd:organisationName/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'position-name',
            search_paths=[
                u'gmd:positionName/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'contact-info',
            search_paths=[
                u'gmd:contactInfo/gmd:CI_Contact',
                ],
            multiplicity=u'0..1',
            elements=[
                ISOElement(
                    name=u'email',
                    search_paths=[
                        u'gmd:address/gmd:CI_Address/gmd:electronicMailAddress/gco'
                        u':CharacterString/text()',
                        ],
                    multiplicity=u'0..1',
                    ),
                ISOResourceLocator(
                    name=u'online-resource',
                    search_paths=[
                        u'gmd:onlineResource/gmd:CI_OnlineResource',
                        ],
                    multiplicity=u'0..1',
                    ),

                ]
            ),
        ISOElement(
            name=u'role',
            search_paths=[
                u'gmd:role/gmd:CI_RoleCode/@codeListValue',
                ],
            multiplicity=u'0..1',
            ),
        ]


class ISODataFormat(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'name',
            search_paths=[
                u'gmd:name/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'version',
            search_paths=[
                u'gmd:version/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ]


class ISOReferenceDate(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'type',
            search_paths=[
                u'gmd:dateType/gmd:CI_DateTypeCode/@codeListValue',
                u'gmd:dateType/gmd:CI_DateTypeCode/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'value',
            search_paths=[
                u'gmd:date/gco:Date/text()',
                u'gmd:date/gco:DateTime/text()',
                ],
            multiplicity=u'1',
            ),
        ]


class ISOCoupledResources(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'title',
            search_paths=[
                u'@xlink:title',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'href',
            search_paths=[
                u'@xlink:href',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'uuid',
            search_paths=[
                u'@uuidref',
                ],
            multiplicity=u'*',
            ),

        ]


class ISOBoundingBox(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'west',
            search_paths=[
                u'gmd:westBoundLongitude/gco:Decimal/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'east',
            search_paths=[
                u'gmd:eastBoundLongitude/gco:Decimal/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'north',
            search_paths=[
                u'gmd:northBoundLatitude/gco:Decimal/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'south',
            search_paths=[
                u'gmd:southBoundLatitude/gco:Decimal/text()',
                ],
            multiplicity=u'1',
            ),
        ]


class ISOBrowseGraphic(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'file',
            search_paths=[
                u'gmd:fileName/gco:CharacterString/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'description',
            search_paths=[
                u'gmd:fileDescription/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'type',
            search_paths=[
                u'gmd:fileType/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ]


class ISOKeyword(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'keyword',
            search_paths=[
                u'gmd:keyword/gco:CharacterString/text()',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'type',
            search_paths=[
                u'gmd:type/gmd:MD_KeywordTypeCode/@codeListValue',
                u'gmd:type/gmd:MD_KeywordTypeCode/text()',
                ],
            multiplicity=u'0..1',
            ),
        # If Thesaurus information is needed at some point, this is the
        # place to add it
        ]


class ISOUsage(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'usage',
            search_paths=[
                u'gmd:specificUsage/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOResponsibleParty(
            name=u'contact-info',
            search_paths=[
                u'gmd:userContactInfo/gmd:CI_ResponsibleParty',
                ],
            multiplicity=u'0..1',
            ),

        ]


class ISOAggregationInfo(ISOElement):
    ''' '''

    elements = [
        ISOElement(
            name=u'aggregate-dataset-name',
            search_paths=[
                u'gmd:aggregateDatasetName/gmd:CI_Citation/gmd:title/gco'
                u':CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'aggregate-dataset-identifier',
            search_paths=[
                u'gmd:aggregateDatasetIdentifier/gmd:MD_Identifier/gmd:code/gco'
                u':CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'association-type',
            search_paths=[
                u'gmd:associationType/gmd:DS_AssociationTypeCode/@codeListValue',
                u'gmd:associationType/gmd:DS_AssociationTypeCode/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'initiative-type',
            search_paths=[
                u'gmd:initiativeType/gmd:DS_InitiativeTypeCode/@codeListValue',
                u'gmd:initiativeType/gmd:DS_InitiativeTypeCode/text()',
                ],
            multiplicity=u'0..1',
            ),
        ]


class ISODocument(MappedXmlDocument):
    ''' '''

    # Attribute specifications from "XPaths for GEMINI" by Peter Parslow.

    elements = [
        ISOElement(
            name=u'guid',
            search_paths=u'gmd:fileIdentifier/gco:CharacterString/text()',
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'metadata-language',
            search_paths=[
                u'gmd:language/gmd:LanguageCode/@codeListValue',
                u'gmd:language/gmd:LanguageCode/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'metadata-standard-name',
            search_paths=u'gmd:metadataStandardName/gco:CharacterString/text()',
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'metadata-standard-version',
            search_paths=u'gmd:metadataStandardVersion/gco:CharacterString/text()',
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'resource-type',
            search_paths=[
                u'gmd:hierarchyLevel/gmd:MD_ScopeCode/@codeListValue',
                u'gmd:hierarchyLevel/gmd:MD_ScopeCode/text()',
                ],
            multiplicity=u'*',
            ),
        ISOResponsibleParty(
            name=u'metadata-point-of-contact',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:pointOfContact'
                u'/gmd:CI_ResponsibleParty',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':pointOfContact/gmd:CI_ResponsibleParty',
                ],
            multiplicity=u'1..*',
            ),
        ISOElement(
            name=u'metadata-date',
            search_paths=[
                u'gmd:dateStamp/gco:DateTime/text()',
                u'gmd:dateStamp/gco:Date/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'spatial-reference-system',
            search_paths=[
                u'gmd:referenceSystemInfo/gmd:MD_ReferenceSystem/gmd'
                u':referenceSystemIdentifier/gmd:RS_Identifier/gmd:code/gco'
                u':CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'title',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:title/gco:CharacterString/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:title/gco:CharacterString/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'alternate-title',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:alternateTitle/gco:CharacterString/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:alternateTitle/gco:CharacterString/text()',
                ],
            multiplicity=u'*',
            ),
        ISOReferenceDate(
            name=u'dataset-reference-date',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:date/gmd:CI_Date',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:date/gmd:CI_Date',
                ],
            multiplicity=u'1..*',
            ),
        ISOElement(
            name=u'unique-resource-identifier',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:identifier/gmd:MD_Identifier/gmd:code/gco'
                u':CharacterString/text()',
                u'gmd:identificationInfo/gmd:SV_ServiceIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:identifier/gmd:MD_Identifier/gmd:code/gco'
                u':CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'presentation-form',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:presentationForm/gmd:CI_PresentationFormCode/text()',
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:presentationForm/gmd:CI_PresentationFormCode'
                u'/@codeListValue',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:presentationForm/gmd:CI_PresentationFormCode/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:citation/gmd'
                u':CI_Citation/gmd:presentationForm/gmd:CI_PresentationFormCode'
                u'/@codeListValue',

                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'abstract',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:abstract/gco'
                u':CharacterString/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:abstract/gco'
                u':CharacterString/text()',
                ],
            multiplicity=u'1',
            ),
        ISOElement(
            name=u'purpose',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:purpose/gco'
                u':CharacterString/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:purpose/gco'
                u':CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOResponsibleParty(
            name=u'responsible-organisation',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:pointOfContact'
                u'/gmd:CI_ResponsibleParty',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':pointOfContact/gmd:CI_ResponsibleParty',
                u'gmd:contact/gmd:CI_ResponsibleParty',
                ],
            multiplicity=u'1..*',
            ),
        ISOElement(
            name=u'frequency-of-update',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceMaintenance/gmd:MD_MaintenanceInformation/gmd'
                u':maintenanceAndUpdateFrequency/gmd:MD_MaintenanceFrequencyCode'
                u'/@codeListValue',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':resourceMaintenance/gmd:MD_MaintenanceInformation/gmd'
                u':maintenanceAndUpdateFrequency/gmd:MD_MaintenanceFrequencyCode'
                u'/@codeListValue',
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceMaintenance/gmd:MD_MaintenanceInformation/gmd'
                u':maintenanceAndUpdateFrequency/gmd:MD_MaintenanceFrequencyCode/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':resourceMaintenance/gmd:MD_MaintenanceInformation/gmd'
                u':maintenanceAndUpdateFrequency/gmd:MD_MaintenanceFrequencyCode/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'maintenance-note',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceMaintenance/gmd:MD_MaintenanceInformation/gmd'
                u':maintenanceNote/gco:CharacterString/text()',
                u'gmd:identificationInfo/gmd:SV_ServiceIdentification/gmd'
                u':resourceMaintenance/gmd:MD_MaintenanceInformation/gmd'
                u':maintenanceNote/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'progress',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:status/gmd'
                u':MD_ProgressCode/@codeListValue',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:status/gmd'
                u':MD_ProgressCode/@codeListValue',
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:status/gmd'
                u':MD_ProgressCode/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:status/gmd'
                u':MD_ProgressCode/text()',
                ],
            multiplicity=u'*',
            ),
        ISOKeyword(
            name=u'keywords',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':descriptiveKeywords/gmd:MD_Keywords',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':descriptiveKeywords/gmd:MD_Keywords',
                ],
            multiplicity=u'*'
            ),
        ISOElement(
            name=u'keyword-inspire-theme',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':descriptiveKeywords/gmd:MD_Keywords/gmd:keyword/gco:CharacterString'
                u'/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':descriptiveKeywords/gmd:MD_Keywords/gmd:keyword/gco:CharacterString'
                u'/text()',
                ],
            multiplicity=u'*',
            ),
        # Deprecated: kept for backwards compatibilty
        ISOElement(
            name=u'keyword-controlled-other',
            search_paths=[
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:keywords/gmd'
                u':MD_Keywords/gmd:keyword/gco:CharacterString/text()',
                ],
            multiplicity=u'*',
            ),
        ISOUsage(
            name=u'usage',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceSpecificUsage/gmd:MD_Usage',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':resourceSpecificUsage/gmd:MD_Usage',
                ],
            multiplicity=u'*'
            ),
        ISOElement(
            name=u'limitations-on-public-access',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceConstraints/gmd:MD_LegalConstraints/gmd:otherConstraints'
                u'/gco:CharacterString/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':resourceConstraints/gmd:MD_LegalConstraints/gmd:otherConstraints'
                u'/gco:CharacterString/text()',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'access-constraints',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceConstraints/gmd:MD_LegalConstraints/gmd:accessConstraints'
                u'/gmd:MD_RestrictionCode/@codeListValue',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':resourceConstraints/gmd:MD_LegalConstraints/gmd:accessConstraints'
                u'/gmd:MD_RestrictionCode/@codeListValue',
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceConstraints/gmd:MD_LegalConstraints/gmd:accessConstraints'
                u'/gmd:MD_RestrictionCode/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':resourceConstraints/gmd:MD_LegalConstraints/gmd:accessConstraints'
                u'/gmd:MD_RestrictionCode/text()',
                ],
            multiplicity=u'*',
            ),

        ISOElement(
            name=u'use-constraints',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':resourceConstraints/gmd:MD_Constraints/gmd:useLimitation/gco'
                u':CharacterString/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':resourceConstraints/gmd:MD_Constraints/gmd:useLimitation/gco'
                u':CharacterString/text()',
                ],
            multiplicity=u'*',
            ),
        ISOAggregationInfo(
            name=u'aggregation-info',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:aggregationInfo'
                u'/gmd:MD_AggregateInformation',
                u'gmd:identificationInfo/gmd:SV_ServiceIdentification/gmd'
                u':aggregationInfo/gmd:MD_AggregateInformation',
                ],
            multiplicity=u'*'
            ),
        ISOElement(
            name=u'spatial-data-service-type',
            search_paths=[
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:serviceType'
                u'/gco:LocalName/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'spatial-resolution',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':spatialResolution/gmd:MD_Resolution/gmd:distance/gco:Distance/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':spatialResolution/gmd:MD_Resolution/gmd:distance/gco:Distance/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'spatial-resolution-units',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':spatialResolution/gmd:MD_Resolution/gmd:distance/gco:Distance/@uom',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':spatialResolution/gmd:MD_Resolution/gmd:distance/gco:Distance/@uom',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'equivalent-scale',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':spatialResolution/gmd:MD_Resolution/gmd:equivalentScale/gmd'
                u':MD_RepresentativeFraction/gmd:denominator/gco:Integer/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':spatialResolution/gmd:MD_Resolution/gmd:equivalentScale/gmd'
                u':MD_RepresentativeFraction/gmd:denominator/gco:Integer/text()',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'dataset-language',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:language/gmd'
                u':LanguageCode/@codeListValue',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:language/gmd'
                u':LanguageCode/@codeListValue',
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:language/gmd'
                u':LanguageCode/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd:language/gmd'
                u':LanguageCode/text()',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'topic-category',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:topicCategory'
                u'/gmd:MD_TopicCategoryCode/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':topicCategory/gmd:MD_TopicCategoryCode/text()',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'extent-controlled',
            search_paths=[
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'extent-free-text',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:extent/gmd'
                u':EX_Extent/gmd:geographicElement/gmd:EX_GeographicDescription/gmd'
                u':geographicIdentifier/gmd:MD_Identifier/gmd:code/gco:CharacterString'
                u'/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gmd'
                u':EX_Extent/gmd:geographicElement/gmd:EX_GeographicDescription/gmd'
                u':geographicIdentifier/gmd:MD_Identifier/gmd:code/gco:CharacterString'
                u'/text()',
                ],
            multiplicity=u'*',
            ),
        ISOBoundingBox(
            name=u'bbox',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:extent/gmd'
                u':EX_Extent/gmd:geographicElement/gmd:EX_GeographicBoundingBox',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gmd'
                u':EX_Extent/gmd:geographicElement/gmd:EX_GeographicBoundingBox',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'temporal-extent-begin',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent/gml'
                u':TimePeriod/gml:beginPosition/text()',
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent'
                u'/gml32:TimePeriod/gml32:beginPosition/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent/gml'
                u':TimePeriod/gml:beginPosition/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent'
                u'/gml32:TimePeriod/gml32:beginPosition/text()',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'temporal-extent-end',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent/gml'
                u':TimePeriod/gml:endPosition/text()',
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent'
                u'/gml32:TimePeriod/gml32:endPosition/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent/gml'
                u':TimePeriod/gml:endPosition/text()',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gmd'
                u':EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent/gmd:extent'
                u'/gml32:TimePeriod/gml32:endPosition/text()',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'vertical-extent',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:extent/gmd'
                u':EX_Extent/gmd:verticalElement/gmd:EX_VerticalExtent',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:extent/gmd'
                u':EX_Extent/gmd:verticalElement/gmd:EX_VerticalExtent',
                ],
            multiplicity=u'*',
            ),
        ISOCoupledResources(
            name=u'coupled-resource',
            search_paths=[
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/srv:operatesOn',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'additional-information-source',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd'
                u':supplementalInformation/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISODataFormat(
            name=u'data-format',
            search_paths=[
                u'gmd:distributionInfo/gmd:MD_Distribution/gmd:distributionFormat/gmd'
                u':MD_Format',
                ],
            multiplicity=u'*',
            ),
        ISOResponsibleParty(
            name=u'distributor',
            search_paths=[
                u'gmd:distributionInfo/gmd:MD_Distribution/gmd:distributor/gmd'
                u':MD_Distributor/gmd:distributorContact/gmd:CI_ResponsibleParty',
                ],
            multiplicity=u'*',
            ),
        ISOResourceLocator(
            name=u'resource-locator',
            search_paths=[
                u'gmd:distributionInfo/gmd:MD_Distribution/gmd:transferOptions/gmd'
                u':MD_DigitalTransferOptions/gmd:onLine/gmd:CI_OnlineResource',
                u'gmd:distributionInfo/gmd:MD_Distribution/gmd:distributor/gmd'
                u':MD_Distributor/gmd:distributorTransferOptions/gmd'
                u':MD_DigitalTransferOptions/gmd:onLine/gmd:CI_OnlineResource'
                ],
            multiplicity=u'*',
            ),
        ISOResourceLocator(
            name=u'resource-locator-identification',
            search_paths=[
                u'gmd:identificationInfo//gmd:CI_OnlineResource',
                ],
            multiplicity=u'*',
            ),
        ISOElement(
            name=u'conformity-specification',
            search_paths=[
                u'gmd:dataQualityInfo/gmd:DQ_DataQuality/gmd:report/gmd'
                u':DQ_DomainConsistency/gmd:result/gmd:DQ_ConformanceResult/gmd'
                u':specification',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'conformity-pass',
            search_paths=[
                u'gmd:dataQualityInfo/gmd:DQ_DataQuality/gmd:report/gmd'
                u':DQ_DomainConsistency/gmd:result/gmd:DQ_ConformanceResult/gmd:pass'
                u'/gco:Boolean/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'conformity-explanation',
            search_paths=[
                u'gmd:dataQualityInfo/gmd:DQ_DataQuality/gmd:report/gmd'
                u':DQ_DomainConsistency/gmd:result/gmd:DQ_ConformanceResult/gmd'
                u':explanation/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOElement(
            name=u'lineage',
            search_paths=[
                u'gmd:dataQualityInfo/gmd:DQ_DataQuality/gmd:lineage/gmd:LI_Lineage'
                u'/gmd:statement/gco:CharacterString/text()',
                ],
            multiplicity=u'0..1',
            ),
        ISOBrowseGraphic(
            name=u'browse-graphic',
            search_paths=[
                u'gmd:identificationInfo/gmd:MD_DataIdentification/gmd:graphicOverview'
                u'/gmd:MD_BrowseGraphic',
                u'gmd:identificationInfo/srv:SV_ServiceIdentification/gmd'
                u':graphicOverview/gmd:MD_BrowseGraphic',
                ],
            multiplicity=u'*',
            ),

        ]

    def infer_values(self, values):
        '''

        :param values: 

        '''
        # Todo: Infer name.
        self.infer_date_released(values)
        self.infer_date_updated(values)
        self.infer_date_created(values)
        self.infer_url(values)
        # Todo: Infer resources.
        self.infer_tags(values)
        self.infer_publisher(values)
        self.infer_contact(values)
        self.infer_contact_email(values)
        return values

    def infer_date_released(self, values):
        '''

        :param values: 

        '''
        value = u''
        for date in values[u'dataset-reference-date']:
            if date[u'type'] == u'publication':
                value = date[u'value']
                break
        values[u'date-released'] = value

    def infer_date_updated(self, values):
        '''

        :param values: 

        '''
        value = u''
        dates = []
        # Use last of several multiple revision dates.
        for date in values[u'dataset-reference-date']:
            if date[u'type'] == u'revision':
                dates.append(date[u'value'])

        if len(dates):
            if len(dates) > 1:
                dates.sort(reverse=True)
            value = dates[0]

        values[u'date-updated'] = value

    def infer_date_created(self, values):
        '''

        :param values: 

        '''
        value = u''
        for date in values[u'dataset-reference-date']:
            if date[u'type'] == u'creation':
                value = date[u'value']
                break
        values[u'date-created'] = value

    def infer_url(self, values):
        '''

        :param values: 

        '''
        value = u''
        for locator in values[u'resource-locator']:
            if locator[u'function'] == u'information':
                value = locator[u'url']
                break
        values[u'url'] = value

    def infer_tags(self, values):
        '''

        :param values: 

        '''
        tags = []
        for key in [u'keyword-inspire-theme', u'keyword-controlled-other']:
            for item in values[key]:
                if item not in tags:
                    tags.append(item)
        values[u'tags'] = tags

    def infer_publisher(self, values):
        '''

        :param values: 

        '''
        value = u''
        for responsible_party in values[u'responsible-organisation']:
            if responsible_party[u'role'] == u'publisher':
                value = responsible_party[u'organisation-name']
            if value:
                break
        values[u'publisher'] = value

    def infer_contact(self, values):
        '''

        :param values: 

        '''
        value = u''
        for responsible_party in values[u'responsible-organisation']:
            value = responsible_party[u'organisation-name']
            if value:
                break
        values[u'contact'] = value

    def infer_contact_email(self, values):
        '''

        :param values: 

        '''
        value = u''
        for responsible_party in values[u'responsible-organisation']:
            if isinstance(responsible_party, dict) and \
                    isinstance(responsible_party.get(u'contact-info'), dict) and \
                    responsible_party[u'contact-info'].has_key(u'email'):
                value = responsible_party[u'contact-info'][u'email']
                if value:
                    break
        values[u'contact-email'] = value


class GeminiDocument(ISODocument):
    '''For backwards compatibility'''

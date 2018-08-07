#!/usr/bin/env python
# encoding: utf-8

from setuptools import find_packages, setup

version = u'0.2'

setup(
    name=u'ckanext-spatial',
    version=version,
    description=u'Geo-related plugins for CKAN',
    long_description=u'',
    classifiers=[],
    # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords=u'',
    author=u'Open Knowledge Foundation',
    author_email=u'info@okfn.org',
    url=u'http://okfn.org',
    license=u'AGPL',
    packages=find_packages(exclude=[u'ez_setup', u'examples', u'tests']),
    namespace_packages=[u'ckanext', u'ckanext.spatial'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        # -*- Extra requirements: -*-
        ],
    entry_points= \
        u'''
        [ckan.plugins]
        spatial_metadata=ckanext.spatial.plugin:SpatialMetadata
        spatial_query=ckanext.spatial.plugin:SpatialQuery
        spatial_harvest_metadata_api=ckanext.spatial.plugin:HarvestMetadataApi
    
        csw_harvester=ckanext.spatial.harvesters:CSWHarvester
        waf_harvester=ckanext.spatial.harvesters:WAFHarvester
        doc_harvester=ckanext.spatial.harvesters:DocHarvester
    
        # Legacy harvesters
        gemini_csw_harvester=ckanext.spatial.harvesters.gemini:GeminiCswHarvester
        gemini_doc_harvester=ckanext.spatial.harvesters.gemini:GeminiDocHarvester
        gemini_waf_harvester=ckanext.spatial.harvesters.gemini:GeminiWafHarvester
    
        [paste.paster_command]
        spatial=ckanext.spatial.commands.spatial:Spatial
        ckan-pycsw=ckanext.spatial.commands.csw:Pycsw
        validation=ckanext.spatial.commands.validation:Validation
    
        [ckan.test_plugins]
        test_spatial_plugin = ckanext.spatial.tests.test_plugin.plugin:TestSpatialPlugin
    
        ''',
    )

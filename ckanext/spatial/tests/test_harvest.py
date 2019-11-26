#!/usr/bin/env python
# encoding: utf-8

from datetime import date, datetime

import lxml
from ckanext.harvest.model import (HarvestJob, HarvestObject, HarvestSource)
from ckanext.spatial.harvesters.base import SpatialHarvester
from ckanext.spatial.harvesters.gemini import (GeminiDocHarvester, GeminiHarvester,
                                               GeminiWafHarvester)
from ckanext.spatial.tests.base import SpatialTestBase
from ckanext.spatial.validation import Validators
from nose.plugins.skip import SkipTest
from nose.tools import assert_equal, assert_in, assert_raises

from ckan import model
from ckan.logic.schema import default_update_package_schema
from ckan.model import Package, Session
from ckan.plugins import toolkit
from xml_file_server import serve

serve()


class HarvestFixtureBase(SpatialTestBase):
    ''' '''

    def setup(self):
        ''' '''
        # Add sysadmin user
        harvest_user = model.User(name=u'harvest', password=u'test', sysadmin=True)
        Session.add(harvest_user)
        Session.commit()

        package_schema = default_update_package_schema()
        self.context = {
            u'user': u'harvest',
            u'schema': package_schema,
            u'api_version': u'2'
            }

    def teardown(self):
        ''' '''

    model.repo.rebuild_db()

    def _create_job(self, source_id):
        '''

        :param source_id: 

        '''
        # Create a job
        context = {
            u'user': u'harvest'
            }

        job_dict = toolkit.get_action(u'harvest_job_create')(context, {
            u'source_id': source_id
            })
        job = HarvestJob.get(job_dict[u'id'])
        assert job

        return job

    def _create_source_and_job(self, source_fixture):
        '''

        :param source_fixture: 

        '''
        context = {
            u'user': u'harvest'
            }

        if toolkit.config.get(u'ckan.harvest.auth.profile') == u'publisher' \
                and not u'publisher_id' in source_fixture:
            source_fixture[u'publisher_id'] = self.publisher.id

        source_dict = toolkit.get_action(u'harvest_source_create')(context,
                                                                   source_fixture)
        source = HarvestSource.get(source_dict[u'id'])
        assert source

        job = self._create_job(source.id)

        return source, job

    def _run_job_for_single_document(self, job, force_import=False,
                                     expect_gather_errors=False,
                                     expect_obj_errors=False):
        '''

        :param job: 
        :param force_import:  (Default value = False)
        :param expect_gather_errors:  (Default value = False)
        :param expect_obj_errors:  (Default value = False)

        '''

        harvester = GeminiDocHarvester()

        harvester.force_import = force_import

        object_ids = harvester.gather_stage(job)
        assert object_ids, len(object_ids) == 1
        if expect_gather_errors:
            assert len(job.gather_errors) > 0
        else:
            assert len(job.gather_errors) == 0

        assert harvester.fetch_stage(object_ids) == True

        obj = HarvestObject.get(object_ids[0])
        assert obj, obj.content

        harvester.import_stage(obj)
        Session.refresh(obj)
        if expect_obj_errors:
            assert len(obj.errors) > 0
        else:
            assert len(obj.errors) == 0

        job.status = u'Finished'
        job.save()

        return obj


class TestHarvest(HarvestFixtureBase):
    ''' '''

    @classmethod
    def setup_class(cls):
        ''' '''
        SpatialHarvester._validator = Validators(profiles=[u'gemini2'])
        HarvestFixtureBase.setup_class()

    def test_harvest_basic(self):
        ''' '''

        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1-waf/index.html',
            u'source_type': u'gemini-waf'
            }

        source, job = self._create_source_and_job(source_fixture)

        harvester = GeminiWafHarvester()

        # We need to send an actual job, not the dict
        object_ids = harvester.gather_stage(job)

        assert len(object_ids) == 2

        # Fetch stage always returns True for Waf harvesters
        assert harvester.fetch_stage(object_ids) == True

        objects = []
        for object_id in object_ids:
            obj = HarvestObject.get(object_id)
            assert obj
            objects.append(obj)
            harvester.import_stage(obj)

        pkgs = Session.query(Package).filter(Package.type != u'harvest').all()

        assert_equal(len(pkgs), 2)

        pkg_ids = [pkg.id for pkg in pkgs]

        for obj in objects:
            assert obj.current == True
            assert obj.package_id in pkg_ids

    def test_harvest_fields_service(self):
        ''' '''

        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/service1.xml',
            u'source_type': u'gemini-single'
            }

        source, job = self._create_source_and_job(source_fixture)

        harvester = GeminiDocHarvester()

        object_ids = harvester.gather_stage(job)
        assert object_ids, len(object_ids) == 1

        # No gather errors
        assert len(job.gather_errors) == 0

        # Fetch stage always returns True for Single Doc harvesters
        assert harvester.fetch_stage(object_ids) == True

        obj = HarvestObject.get(object_ids[0])
        assert obj, obj.content
        assert obj.guid == u'test-service-1'

        harvester.import_stage(obj)

        # No object errors
        assert len(obj.errors) == 0

        package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': obj.package_id
            })

        assert package_dict

        expected = {
            u'name': u'one-scotland-address-gazetteer-web-map-service-wms',
            u'title': u'One Scotland Address Gazetteer Web Map Service (WMS)',
            u'tags': [u'Addresses', u'Scottish National Gazetteer'],
            u'notes': u'This service displays its contents at larger scale than '
                      u'1:10000. [edited]',
            }

        for key, value in expected.iteritems():
            if not package_dict[key] == value:
                raise AssertionError(u'Unexpected value for %s: %s (was expecting %s)'
                                     % \
                                     (key, package_dict[key], value))

        if toolkit.config.get(u'ckan.harvest.auth.profile') == u'publisher':
            assert package_dict[u'groups'] == [self.publisher.id]

        expected_extras = {
            # Basic
            u'harvest_object_id': obj.id,
            u'guid': obj.guid,
            u'UKLP': u'True',
            u'resource-type': u'service',
            u'access_constraints': u'["No restriction on public access"]',
            u'responsible-party': u'The Improvement Service (owner)',
            u'provider': u'The Improvement Service',
            u'contact-email': u'OSGCM@improvementservice.org.uk',
            # Spatial
            u'bbox-east-long': u'0.5242365625',
            u'bbox-north-lat': u'61.0243',
            u'bbox-south-lat': u'54.4764484375',
            u'bbox-west-long': u'-9.099786875',
            u'spatial': u'{"type": "Polygon", "coordinates": [[[0.5242365625, '
                        u'54.4764484375], [-9.099786875, 54.4764484375], '
                        u'[-9.099786875, 61.0243], [0.5242365625, 61.0243], '
                        u'[0.5242365625, 54.4764484375]]]}',
            # Other
            u'coupled-resource': u'[{"href": ['
                                 u'"http://scotgovsdi.edina.ac.uk/srv/en/csw?service'
                                 u'=CSW&request=GetRecordById&version=2.0.2&outputSchema=http://www.isotc211.org/2005/gmd&elementSetName=full&id=250ea276-48e2-4189-8a89-fcc4ca92d652"], "uuid": ["250ea276-48e2-4189-8a89-fcc4ca92d652"], "title": []}]',
            u'dataset-reference-date': u'[{"type": "publication", "value": '
                                       u'"2011-09-08"}]',
            u'frequency-of-update': u'daily',
            u'licence': u'["Use of the One Scotland Gazetteer data used by this this '
                        u'service is available to any organisation that is a member of '
                        u'the One Scotland Mapping Agreement. It is not currently '
                        u'commercially available", "http://www.test.gov.uk/licenseurl"]',
            u'licence_url': u'http://www.test.gov.uk/licenseurl',
            u'metadata-date': u'2011-09-08T16:07:32',
            u'metadata-language': u'eng',
            u'spatial-data-service-type': u'other',
            u'spatial-reference-system': u'OSGB 1936 / British National Grid ('
                                         u'EPSG:27700)',
            u'temporal_coverage-from': u'["1904-06-16"]',
            u'temporal_coverage-to': u'["2004-06-16"]',
            }

        for key, value in expected_extras.iteritems():
            if not key in package_dict[u'extras']:
                raise AssertionError(u'Extra %s not present in package' % key)

            if not package_dict[u'extras'][key] == value:
                raise AssertionError(
                    u'Unexpected value for extra %s: %s (was expecting %s)' % \
                    (key, package_dict[u'extras'][key], value))

        expected_resource = {
            u'ckan_recommended_wms_preview': u'True',
            u'description': u'Link to the GetCapabilities request for this service',
            u'name': u'Web Map Service (WMS)',
            u'resource_locator_function': u'download',
            u'resource_locator_protocol': u'OGC:WMS-1.3.0-http-get-capabilities',
            u'resource_type': None,
            u'size': None,
            u'url': u'http://127.0.0.1:8999/wms/capabilities.xml',
            u'verified': u'True',
            }

        resource = package_dict[u'resources'][0]
        for key, value in expected_resource.iteritems():
            if not resource[key] == value:
                raise AssertionError(
                    u'Unexpected value in resource for %s: %s (was expecting %s)' % \
                    (key, resource[key], value))
        assert datetime.strptime(resource[u'verified_date'],
                                 u'%Y-%m-%dT%H:%M:%S.%f').date() == date.today()
        assert resource[u'format'].lower() == u'wms'

    def test_harvest_fields_dataset(self):
        ''' '''

        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/dataset1.xml',
            u'source_type': u'gemini-single'
            }

        source, job = self._create_source_and_job(source_fixture)

        harvester = GeminiDocHarvester()

        object_ids = harvester.gather_stage(job)
        assert object_ids, len(object_ids) == 1

        # No gather errors
        assert len(job.gather_errors) == 0

        # Fetch stage always returns True for Single Doc harvesters
        assert harvester.fetch_stage(object_ids) == True

        obj = HarvestObject.get(object_ids[0])
        assert obj, obj.content
        assert obj.guid == u'test-dataset-1'

        harvester.import_stage(obj)

        # No object errors
        assert len(obj.errors) == 0

        package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': obj.package_id
            })

        assert package_dict

        expected = {
            u'name': u'country-parks-scotland',
            u'title': u'Country Parks (Scotland)',
            u'tags': [u'Nature conservation'],
            u'notes': u'Parks are set up by Local Authorities to provide open-air '
                      u'recreation facilities close to towns and cities. [edited]'
            }

        for key, value in expected.iteritems():
            if not package_dict[key] == value:
                raise AssertionError(u'Unexpected value for %s: %s (was expecting %s)'
                                     % \
                                     (key, package_dict[key], value))

        if toolkit.config.get(u'ckan.harvest.auth.profile') == u'publisher':
            assert package_dict[u'groups'] == [self.publisher.id]

        expected_extras = {
            # Basic
            u'harvest_object_id': obj.id,
            u'guid': obj.guid,
            u'resource-type': u'dataset',
            u'responsible-party': u'Scottish Natural Heritage (custodian, distributor)',
            u'access_constraints': u'["Copyright Scottish Natural Heritage"]',
            u'contact-email': u'data_supply@snh.gov.uk',
            u'provider': u'',
            # Spatial
            u'bbox-east-long': u'0.205857204',
            u'bbox-north-lat': u'61.06066944',
            u'bbox-south-lat': u'54.529947158',
            u'bbox-west-long': u'-8.97114288',
            u'spatial': u'{"type": "Polygon", "coordinates": [[[0.205857204, '
                        u'54.529947158], [-8.97114288, 54.529947158], [-8.97114288, '
                        u'61.06066944], [0.205857204, 61.06066944], [0.205857204, '
                        u'54.529947158]]]}',
            # Other
            u'coupled-resource': u'[]',
            u'dataset-reference-date': u'[{"type": "creation", "value": "2004-02"}, '
                                       u'{"type": "revision", "value": "2006-07-03"}]',
            u'frequency-of-update': u'irregular',
            u'licence': u'["Reference and PSMA Only", '
                        u'"http://www.test.gov.uk/licenseurl"]',
            u'licence_url': u'http://www.test.gov.uk/licenseurl',
            u'metadata-date': u'2011-09-23T10:06:08',
            u'metadata-language': u'eng',
            u'spatial-reference-system': u'urn:ogc:def:crs:EPSG::27700',
            u'temporal_coverage-from': u'["1998"]',
            u'temporal_coverage-to': u'["2010"]',
            }

        for key, value in expected_extras.iteritems():
            if not key in package_dict[u'extras']:
                raise AssertionError(u'Extra %s not present in package' % key)

            if not package_dict[u'extras'][key] == value:
                raise AssertionError(
                    u'Unexpected value for extra %s: %s (was expecting %s)' % \
                    (key, package_dict[u'extras'][key], value))

        expected_resource = {
            u'description': u'Test Resource Description',
            u'format': u'',
            u'name': u'Test Resource Name',
            u'resource_locator_function': u'download',
            u'resource_locator_protocol': u'test-protocol',
            u'resource_type': None,
            u'size': None,
            u'url': u'https://gateway.snh.gov.uk/pls/apex_ddtdb2/f?p=101',
            }

        resource = package_dict[u'resources'][0]
        for key, value in expected_resource.iteritems():
            if not resource[key] == value:
                raise AssertionError(
                    u'Unexpected value in resource for %s: %s (was expecting %s)' % \
                    (key, resource[key], value))

    def test_harvest_error_bad_xml(self):
        ''' '''
        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/error_bad_xml.xml',
            u'source_type': u'gemini-single'
            }

        source, job = self._create_source_and_job(source_fixture)

        harvester = GeminiDocHarvester()

        try:
            object_ids = harvester.gather_stage(job)
        except lxml.etree.XMLSyntaxError:
            # this only occurs in debug_exception_mode
            pass
        else:
            assert object_ids is None

        # Check gather errors
        assert len(job.gather_errors) == 1
        assert job.gather_errors[0].harvest_job_id == job.id
        assert u'Error parsing the document' in job.gather_errors[0].message

    def test_harvest_error_404(self):
        ''' '''
        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/not_there.xml',
            u'source_type': u'gemini-single'
            }

        source, job = self._create_source_and_job(source_fixture)

        harvester = GeminiDocHarvester()

        object_ids = harvester.gather_stage(job)
        assert object_ids is None

        # Check gather errors
        assert len(job.gather_errors) == 1
        assert job.gather_errors[0].harvest_job_id == job.id
        assert u'Unable to get content for URL' in job.gather_errors[0].message

    def test_harvest_error_validation(self):
        ''' '''

        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/error_validation.xml',
            u'source_type': u'gemini-single'
            }

        source, job = self._create_source_and_job(source_fixture)

        harvester = GeminiDocHarvester()

        object_ids = harvester.gather_stage(job)

        # Right now the import process goes ahead even with validation errors
        assert object_ids, len(object_ids) == 1

        # No gather errors
        assert len(job.gather_errors) == 0

        # Fetch stage always returns True for Single Doc harvesters
        assert harvester.fetch_stage(object_ids) == True

        obj = HarvestObject.get(object_ids[0])
        assert obj, obj.content
        assert obj.guid == u'test-error-validation-1'

        harvester.import_stage(obj)

        # Check errors
        assert len(obj.errors) == 1
        assert obj.errors[0].harvest_object_id == obj.id

        message = obj.errors[0].message

        assert_in(u'One email address shall be provided', message)
        assert_in(
            u'Service type shall be one of \'discovery\', \'view\', \'download\', '
            u'\'transformation\', \'invoke\' or \'other\' following INSPIRE generic '
            u'names',
            message)
        assert_in(
            u'Limitations on public access code list value shall be '
            u'\'otherRestrictions\'',
            message)
        assert_in(u'One organisation name shall be provided', message)

    def test_harvest_update_records(self):
        ''' '''

        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/dataset1.xml',
            u'source_type': u'gemini-single'
            }

        source, first_job = self._create_source_and_job(source_fixture)

        first_obj = self._run_job_for_single_document(first_job)

        first_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was created
        assert first_package_dict
        assert first_obj.current == True
        assert first_obj.package

        # Create and run a second job, the package should not be updated
        second_job = self._create_job(source.id)

        second_obj = self._run_job_for_single_document(second_job)

        Session.remove()
        Session.add(first_obj)
        Session.add(second_obj)

        Session.refresh(first_obj)
        Session.refresh(second_obj)

        second_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was not updated
        assert second_package_dict, first_package_dict[u'id'] == second_package_dict[
            u'id']
        assert first_package_dict[u'metadata_modified'] == second_package_dict[
            u'metadata_modified']
        assert not second_obj.package, not second_obj.package_id
        assert second_obj.current == False, first_obj.current == True

        # Create and run a third job, forcing the importing to simulate an update in
        # the package
        third_job = self._create_job(source.id)
        third_obj = self._run_job_for_single_document(third_job, force_import=True)

        # For some reason first_obj does not get updated after the import_stage,
        # and we have to force a refresh to get the actual DB values.
        Session.remove()
        Session.add(first_obj)
        Session.add(second_obj)
        Session.add(third_obj)

        Session.refresh(first_obj)
        Session.refresh(second_obj)
        Session.refresh(third_obj)

        third_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': third_obj.package_id
            })

        # Package was updated
        assert third_package_dict, first_package_dict[u'id'] == third_package_dict[u'id']
        assert third_package_dict[u'metadata_modified'] > second_package_dict[
            u'metadata_modified']
        assert third_obj.package, third_obj.package_id == first_package_dict[u'id']
        assert third_obj.current == True
        assert second_obj.current == False
        assert first_obj.current == False

    def test_harvest_deleted_record(self):
        ''' '''

        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/service1.xml',
            u'source_type': u'gemini-single'
            }

        source, first_job = self._create_source_and_job(source_fixture)

        first_obj = self._run_job_for_single_document(first_job)

        first_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was created
        assert first_package_dict
        assert first_package_dict[u'state'] == u'active'
        assert first_obj.current == True

        # Delete package
        first_package_dict[u'state'] = u'deleted'
        self.context.update({
            u'id': first_package_dict[u'id']
            })
        updated_package_dict = toolkit.get_action(u'package_update_rest')(self.context,
                                                                          first_package_dict)

        # Create and run a second job, the date has not changed, so the package should
        #  not be updated
        # and remain deleted
        first_job.status = u'Finished'
        first_job.save()
        second_job = self._create_job(source.id)

        second_obj = self._run_job_for_single_document(second_job)

        second_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was not updated
        assert second_package_dict, updated_package_dict[u'id'] == second_package_dict[
            u'id']
        assert not second_obj.package, not second_obj.package_id
        assert second_obj.current == False, first_obj.current == True

        # Harvest an updated document, with a more recent modified date, package
        # should be
        # updated and reactivated
        source.url = u'http://127.0.0.1:8999/gemini2.1/service1_newer.xml'
        source.save()

        third_job = self._create_job(source.id)

        third_obj = self._run_job_for_single_document(third_job)

        third_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        Session.remove()
        Session.add(first_obj)
        Session.add(second_obj)
        Session.add(third_obj)

        Session.refresh(first_obj)
        Session.refresh(second_obj)
        Session.refresh(third_obj)

        # Package was updated
        assert third_package_dict, third_package_dict[u'id'] == second_package_dict[
            u'id']
        assert third_obj.package, third_obj.package
        assert third_obj.current == True, second_obj.current == False
        assert first_obj.current == False

        assert u'NEWER' in third_package_dict[u'title']
        assert third_package_dict[u'state'] == u'active'

    def test_harvest_different_sources_same_document(self):
        ''' '''

        # Create source1
        source1_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/source1/same_dataset.xml',
            u'source_type': u'gemini-single'
            }

        source1, first_job = self._create_source_and_job(source1_fixture)

        first_obj = self._run_job_for_single_document(first_job)

        first_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was created
        assert first_package_dict
        assert first_package_dict[u'state'] == u'active'
        assert first_obj.current == True

        # Harvest the same document, unchanged, from another source, the package
        # is not updated.
        # (As of https://github.com/okfn/ckanext-inspire/commit/9fb67
        # we are no longer throwing an exception when this happens)
        source2_fixture = {
            u'title': u'Test Source 2',
            u'name': u'test-source-2',
            u'url': u'http://127.0.0.1:8999/gemini2.1/source2/same_dataset.xml',
            u'source_type': u'gemini-single'
            }

        source2, second_job = self._create_source_and_job(source2_fixture)

        second_obj = self._run_job_for_single_document(second_job)

        second_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was not updated
        assert second_package_dict, first_package_dict[u'id'] == second_package_dict[
            u'id']
        assert first_package_dict[u'metadata_modified'] == second_package_dict[
            u'metadata_modified']
        assert not second_obj.package, not second_obj.package_id
        assert second_obj.current == False, first_obj.current == True

        # Inactivate source1 and reharvest from source2, package should be updated
        third_job = self._create_job(source2.id)
        third_obj = self._run_job_for_single_document(third_job, force_import=True)

        Session.remove()
        Session.add(first_obj)
        Session.add(second_obj)
        Session.add(third_obj)

        Session.refresh(first_obj)
        Session.refresh(second_obj)
        Session.refresh(third_obj)

        third_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was updated
        assert third_package_dict, first_package_dict[u'id'] == third_package_dict[u'id']
        assert third_package_dict[u'metadata_modified'] > second_package_dict[
            u'metadata_modified']
        assert third_obj.package, third_obj.package_id == first_package_dict[u'id']
        assert third_obj.current == True
        assert second_obj.current == False
        assert first_obj.current == False

    def test_harvest_different_sources_same_document_but_deleted_inbetween(self):
        ''' '''

        # Create source1
        source1_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/source1/same_dataset.xml',
            u'source_type': u'gemini-single'
            }

        source1, first_job = self._create_source_and_job(source1_fixture)

        first_obj = self._run_job_for_single_document(first_job)

        first_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was created
        assert first_package_dict
        assert first_package_dict[u'state'] == u'active'
        assert first_obj.current == True

        # Delete/withdraw the package
        first_package_dict = toolkit.get_action(u'package_delete')(self.context, {
            u'id': first_obj.package_id
            })
        first_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Harvest the same document, unchanged, from another source
        source2_fixture = {
            u'title': u'Test Source 2',
            u'name': u'test-source-2',
            u'url': u'http://127.0.0.1:8999/gemini2.1/source2/same_dataset.xml',
            u'source_type': u'gemini-single'
            }

        source2, second_job = self._create_source_and_job(source2_fixture)

        second_obj = self._run_job_for_single_document(second_job)

        second_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # It would be good if the package was updated, but we see that it isn't
        assert second_package_dict, first_package_dict[u'id'] == second_package_dict[
            u'id']
        assert second_package_dict[u'metadata_modified'] == first_package_dict[
            u'metadata_modified']
        assert not second_obj.package
        assert second_obj.current == False
        assert first_obj.current == True

    def test_harvest_moves_sources(self):
        ''' '''

        # Create source1
        source1_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/service1.xml',
            u'source_type': u'gemini-single'
            }

        source1, first_job = self._create_source_and_job(source1_fixture)

        first_obj = self._run_job_for_single_document(first_job)

        first_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was created
        assert first_package_dict
        assert first_package_dict[u'state'] == u'active'
        assert first_obj.current == True

        # Harvest the same document GUID but with a newer date, from another source.
        source2_fixture = {
            u'title': u'Test Source 2',
            u'name': u'test-source-2',
            u'url': u'http://127.0.0.1:8999/gemini2.1/service1_newer.xml',
            u'source_type': u'gemini-single'
            }

        source2, second_job = self._create_source_and_job(source2_fixture)

        second_obj = self._run_job_for_single_document(second_job)

        second_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Now we have two packages
        assert second_package_dict, first_package_dict[u'id'] == second_package_dict[
            u'id']
        assert second_package_dict[u'metadata_modified'] > first_package_dict[
            u'metadata_modified']
        assert second_obj.package
        assert second_obj.current == True
        assert first_obj.current == True
        # so currently, if you move a Gemini between harvest sources you need
        # to update the date to get it to reharvest, and then you should
        # withdraw the package relating to the original harvest source.

    def test_harvest_import_command(self):
        ''' '''

        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/dataset1.xml',
            u'source_type': u'gemini-single'
            }

        source, first_job = self._create_source_and_job(source_fixture)

        first_obj = self._run_job_for_single_document(first_job)

        before_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was created
        assert before_package_dict
        assert first_obj.current == True
        assert first_obj.package

        # Create and run two more jobs, the package should not be updated
        second_job = self._create_job(source.id)
        second_obj = self._run_job_for_single_document(second_job)
        third_job = self._create_job(source.id)
        third_obj = self._run_job_for_single_document(third_job)

        # Run the import command manually
        imported_objects = toolkit.get_action(u'harvest_objects_import')(self.context, {
            u'source_id': source.id
            })
        Session.remove()
        Session.add(first_obj)
        Session.add(second_obj)
        Session.add(third_obj)

        Session.refresh(first_obj)
        Session.refresh(second_obj)
        Session.refresh(third_obj)

        after_package_dict = toolkit.get_action(u'package_show_rest')(self.context, {
            u'id': first_obj.package_id
            })

        # Package was updated, and the current object remains the same
        assert after_package_dict, before_package_dict[u'id'] == after_package_dict[
            u'id']
        assert after_package_dict[u'metadata_modified'] > before_package_dict[
            u'metadata_modified']
        assert third_obj.current == False
        assert second_obj.current == False
        assert first_obj.current == True

        source_dict = toolkit.get_action(u'harvest_source_show')(self.context, {
            u'id': source.id
            })
        assert source_dict[u'status'][u'total_datasets'] == 1


BASIC_GEMINI = u'''<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd" 
xmlns:gco="http://www.isotc211.org/2005/gco">
  <gmd:fileIdentifier xmlns:gml="http://www.opengis.net/gml">
    <gco:CharacterString>e269743a-cfda-4632-a939-0c8416ae801e</gco:CharacterString>
  </gmd:fileIdentifier>
  <gmd:hierarchyLevel>
    <gmd:MD_ScopeCode codeList="http://standards.iso.org/ittf
    /PubliclyAvailableStandards/ISO_19139_Schemas/resources/Codelist/gmxCodelists.xml
    #MD_ScopeCode" codeListValue="service">service</gmd:MD_ScopeCode>
  </gmd:hierarchyLevel>
</gmd:MD_Metadata>'''
GUID = u'e269743a-cfda-4632-a939-0c8416ae801e'
GEMINI_MISSING_GUID = u'''<gmd:MD_Metadata 
xmlns:gmd="http://www.isotc211.org/2005/gmd" 
xmlns:gco="http://www.isotc211.org/2005/gco"/>'''


class TestGatherMethods(HarvestFixtureBase):
    ''' '''

    def setup(self):
        ''' '''
        HarvestFixtureBase.setup(self)
        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/dataset1.xml',
            u'source_type': u'gemini-single'
            }
        source, job = self._create_source_and_job(source_fixture)
        self.harvester = GeminiHarvester()
        self.harvester.harvest_job = job

    def teardown(self):
        ''' '''
        model.repo.rebuild_db()

    def test_get_gemini_string_and_guid(self):
        ''' '''
        res = self.harvester.get_gemini_string_and_guid(BASIC_GEMINI, url=None)
        assert_equal(res, (BASIC_GEMINI, GUID))

    def test_get_gemini_string_and_guid__no_guid(self):
        ''' '''
        res = self.harvester.get_gemini_string_and_guid(GEMINI_MISSING_GUID, url=None)
        assert_equal(res, (GEMINI_MISSING_GUID, u''))

    def test_get_gemini_string_and_guid__non_parsing(self):
        ''' '''
        content = u'<gmd:MD_Metadata xmlns:gmd="http://www.isotc211.org/2005/gmd" ' \
                  u'xmlns:gco="http://www.isotc211.org/2005/gco">'  # no closing tag
        assert_raises(lxml.etree.XMLSyntaxError,
                      self.harvester.get_gemini_string_and_guid, content)

    def test_get_gemini_string_and_guid__empty(self):
        ''' '''
        content = u''
        assert_raises(lxml.etree.XMLSyntaxError,
                      self.harvester.get_gemini_string_and_guid, content)


class TestImportStageTools:
    ''' '''

    def test_licence_url_normal(self):
        ''' '''
        assert_equal(GeminiHarvester._extract_first_licence_url(
            [u'Reference and PSMA Only',
             u'http://www.test.gov.uk/licenseurl']),
            u'http://www.test.gov.uk/licenseurl')

    def test_licence_url_multiple_urls(self):
        ''' '''
        # only the first URL is extracted
        assert_equal(GeminiHarvester._extract_first_licence_url(
            [u'Reference and PSMA Only',
             u'http://www.test.gov.uk/licenseurl',
             u'http://www.test.gov.uk/2nd_licenseurl']),
            u'http://www.test.gov.uk/licenseurl')

    def test_licence_url_embedded(self):
        ''' '''
        # URL is embedded within the text field and not extracted
        assert_equal(GeminiHarvester._extract_first_licence_url(
            [u'Reference and PSMA Only http://www.test.gov.uk/licenseurl']),
            None)

    def test_licence_url_embedded_at_start(self):
        ''' '''
        # URL is embedded at the start of the text field and the
        # whole field is returned. Noting this unusual behaviour
        assert_equal(GeminiHarvester._extract_first_licence_url(
            [u'http://www.test.gov.uk/licenseurl Reference and PSMA Only']),
            u'http://www.test.gov.uk/licenseurl Reference and PSMA Only')

    def test_responsible_organisation_basic(self):
        ''' '''
        responsible_organisation = [{
            u'organisation-name': u'Ordnance Survey',
            u'role': u'owner'
            },
            {
                u'organisation-name': u'Maps Ltd',
                u'role': u'distributor'
                }]
        assert_equal(
            GeminiHarvester._process_responsible_organisation(responsible_organisation),
            (u'Ordnance Survey', [u'Maps Ltd (distributor)',
                                  u'Ordnance Survey (owner)']))

    def test_responsible_organisation_publisher(self):
        ''' '''
        # no owner, so falls back to publisher
        responsible_organisation = [{
            u'organisation-name': u'Ordnance Survey',
            u'role': u'publisher'
            },
            {
                u'organisation-name': u'Maps Ltd',
                u'role': u'distributor'
                }]
        assert_equal(
            GeminiHarvester._process_responsible_organisation(responsible_organisation),
            (u'Ordnance Survey', [u'Maps Ltd (distributor)',
                                  u'Ordnance Survey (publisher)']))

    def test_responsible_organisation_owner(self):
        ''' '''
        # provider is the owner (ignores publisher)
        responsible_organisation = [{
            u'organisation-name': u'Ordnance Survey',
            u'role': u'publisher'
            },
            {
                u'organisation-name': u'Owner',
                u'role': u'owner'
                },
            {
                u'organisation-name': u'Maps Ltd',
                u'role': u'distributor'
                }]
        assert_equal(
            GeminiHarvester._process_responsible_organisation(responsible_organisation),
            (u'Owner', [u'Owner (owner)',
                        u'Maps Ltd (distributor)',
                        u'Ordnance Survey (publisher)',
                        ]))

    def test_responsible_organisation_multiple_roles(self):
        ''' '''
        # provider is the owner (ignores publisher)
        responsible_organisation = [{
            u'organisation-name': u'Ordnance Survey',
            u'role': u'publisher'
            },
            {
                u'organisation-name': u'Ordnance Survey',
                u'role': u'custodian'
                },
            {
                u'organisation-name': u'Distributor',
                u'role': u'distributor'
                }]
        assert_equal(
            GeminiHarvester._process_responsible_organisation(responsible_organisation),
            (u'Ordnance Survey', [u'Distributor (distributor)',
                                  u'Ordnance Survey (publisher, custodian)',
                                  ]))

    def test_responsible_organisation_blank_provider(self):
        ''' '''
        # no owner or publisher, so blank provider
        responsible_organisation = [{
            u'organisation-name': u'Ordnance Survey',
            u'role': u'resourceProvider'
            },
            {
                u'organisation-name': u'Maps Ltd',
                u'role': u'distributor'
                }]
        assert_equal(
            GeminiHarvester._process_responsible_organisation(responsible_organisation),
            (u'', [u'Maps Ltd (distributor)',
                   u'Ordnance Survey (resourceProvider)']))

    def test_responsible_organisation_blank(self):
        ''' '''
        # no owner or publisher, so blank provider
        responsible_organisation = []
        assert_equal(
            GeminiHarvester._process_responsible_organisation(responsible_organisation),
            (u'', []))


class TestValidation(HarvestFixtureBase):
    ''' '''

    @classmethod
    def setup_class(cls):
        ''' '''

        # TODO: Fix these tests, broken since 27c4ee81e
        raise SkipTest(u'Validation tests not working since 27c4ee81e')

        SpatialHarvester._validator = Validators(
            profiles=[u'iso19139eden', u'constraints', u'gemini2'])
        HarvestFixtureBase.setup_class()

    def get_validation_errors(self, validation_test_filename):
        '''

        :param validation_test_filename: 

        '''
        # Create source
        source_fixture = {
            u'title': u'Test Source',
            u'name': u'test-source',
            u'url': u'http://127.0.0.1:8999/gemini2.1/validation/%s' %
                    validation_test_filename,
            u'source_type': u'gemini-single'
            }

        source, job = self._create_source_and_job(source_fixture)

        harvester = GeminiDocHarvester()

        # Gather stage for GeminiDocHarvester includes validation
        object_ids = harvester.gather_stage(job)

        # Check the validation errors
        errors = u'; '.join([gather_error.message for gather_error in job.gather_errors])
        return errors

    def test_01_dataset_fail_iso19139_schema(self):
        ''' '''
        errors = self.get_validation_errors(
            u'01_Dataset_Invalid_XSD_No_Such_Element.xml')
        assert len(errors) > 0
        assert_in(u'Could not get the GUID', errors)

    def test_02_dataset_fail_constraints_schematron(self):
        ''' '''
        errors = self.get_validation_errors(
            u'02_Dataset_Invalid_19139_Missing_Data_Format.xml')
        assert len(errors) > 0
        assert_in(
            u'MD_Distribution / MD_Format: count(distributionFormat + '
            u'distributorFormat) > 0',
            errors)

    def test_03_dataset_fail_gemini_schematron(self):
        ''' '''
        errors = self.get_validation_errors(
            u'03_Dataset_Invalid_GEMINI_Missing_Keyword.xml')
        assert len(errors) > 0
        assert_in(u'Descriptive keywords are mandatory', errors)

    def test_04_dataset_valid(self):
        ''' '''
        errors = self.get_validation_errors(u'04_Dataset_Valid.xml')
        assert len(errors) == 0

    def test_05_series_fail_iso19139_schema(self):
        ''' '''
        errors = self.get_validation_errors(u'05_Series_Invalid_XSD_No_Such_Element.xml')
        assert len(errors) > 0
        assert_in(u'Could not get the GUID', errors)

    def test_06_series_fail_constraints_schematron(self):
        ''' '''
        errors = self.get_validation_errors(
            u'06_Series_Invalid_19139_Missing_Data_Format.xml')
        assert len(errors) > 0
        assert_in(
            u'MD_Distribution / MD_Format: count(distributionFormat + '
            u'distributorFormat) > 0',
            errors)

    def test_07_series_fail_gemini_schematron(self):
        ''' '''
        errors = self.get_validation_errors(
            u'07_Series_Invalid_GEMINI_Missing_Keyword.xml')
        assert len(errors) > 0
        assert_in(u'Descriptive keywords are mandatory', errors)

    def test_08_series_valid(self):
        ''' '''
        errors = self.get_validation_errors(u'08_Series_Valid.xml')
        assert len(errors) == 0

    def test_09_service_fail_iso19139_schema(self):
        ''' '''
        errors = self.get_validation_errors(u'09_Service_Invalid_No_Such_Element.xml')
        assert len(errors) > 0
        assert_in(u'Could not get the GUID', errors)

    def test_10_service_fail_constraints_schematron(self):
        ''' '''
        errors = self.get_validation_errors(
            u'10_Service_Invalid_19139_Level_Description.xml')
        assert len(errors) > 0
        assert_in(
            u"DQ_Scope: 'levelDescription' is mandatory if 'level' notEqual 'dataset' "
            u"or 'series'.",
            errors)

    def test_11_service_fail_gemini_schematron(self):
        ''' '''
        errors = self.get_validation_errors(
            u'11_Service_Invalid_GEMINI_Service_Type.xml')
        assert len(errors) > 0
        assert_in(
            u"Service type shall be one of 'discovery', 'view', 'download', "
            u"'transformation', 'invoke' or 'other' following INSPIRE generic names.",
            errors)

    def test_12_service_valid(self):
        ''' '''
        errors = self.get_validation_errors(u'12_Service_Valid.xml')
        assert len(errors) == 0, errors

    def test_13_dataset_fail_iso19139_schema_2(self):
        ''' '''
        # This test Dataset has srv tags and only Service metadata should.
        errors = self.get_validation_errors(u'13_Dataset_Invalid_Element_srv.xml')
        assert len(errors) > 0
        assert_in(
            u'Element \'{http://www.isotc211.org/2005/srv}SV_ServiceIdentification\': '
            u'This element is not expected.',
            errors)

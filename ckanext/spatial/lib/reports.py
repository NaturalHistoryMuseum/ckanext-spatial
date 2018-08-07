#!/usr/bin/env python
# encoding: utf-8

import logging

from ckanext.harvest.model import HarvestObject
from ckanext.spatial.harvesters import SpatialHarvester
from ckanext.spatial.lib.report import ReportTable
from lxml import etree

from ckan import model


def validation_report(package_id=None):
    '''Looks at every harvested metadata record and compares the
    validation errors that it had on last import and what it would be with
    the current validators. Useful when going to update the validators.
    
    Returns a ReportTable.

    :param package_id:  (Default value = None)

    '''
    log = logging.getLogger(__name__ + u'.validation_report')

    validators = SpatialHarvester()._get_validator()
    log.debug(u'Validators: %r', validators.profiles)

    query = model.Session.query(HarvestObject). \
        filter_by(current=True). \
        order_by(HarvestObject.fetch_finished.desc())

    if package_id:
        query = query.filter(HarvestObject.package_id == package_id)

    report = ReportTable([
        u'Harvest Object id',
        u'GEMINI2 id',
        u'Date fetched',
        u'Dataset name',
        u'Publisher',
        u'Source URL',
        u'Old validation errors',
        u'New validation errors'])

    old_validation_failure_count = 0
    new_validation_failure_count = 0

    for harvest_object in query:
        validation_errors = []
        for err in harvest_object.errors:
            if u'not a valid Gemini' in err.message or \
                    u'Validating against' in err.message:
                validation_errors.append(err.message)
        if validation_errors:
            old_validation_failure_count += 1

        groups = harvest_object.package.get_groups()
        publisher = groups[0].title if groups else u'(none)'

        xml = etree.fromstring(harvest_object.content.encode(u'utf-8'))
        valid, errors = validators.is_valid(xml)
        if not valid:
            new_validation_failure_count += 1

        report.add_row_dict({
            u'Harvest Object id': harvest_object.id,
            u'GEMINI2 id': harvest_object.guid,
            u'Date fetched': harvest_object.fetch_finished,
            u'Dataset name': harvest_object.package.name,
            u'Publisher': publisher,
            u'Source URL': harvest_object.source.url,
            u'Old validation errors': u'; '.join(validation_errors),
            u'New validation errors': u'; '.join(errors),
            })

    log.debug(u'%i results', query.count())
    log.debug(u'%i failed old validation', old_validation_failure_count)
    log.debug(u'%i failed new validation', new_validation_failure_count)
    return report

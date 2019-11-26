#!/usr/bin/env python
# encoding: utf-8

import json
import logging

from ckan.plugins import toolkit

log = logging.getLogger(__name__)


def get_reference_date(date_str):
    '''Gets a reference date extra created by the harvesters and formats it
        nicely for the UI.
    
        Examples:
            [{"type": "creation", "value": "1977"}, {"type": "revision", "value":
            "1981-05-15"}]
            [{"type": "publication", "value": "1977"}]
            [{"type": "publication", "value": "NaN-NaN-NaN"}]
    
        Results
            1977 (creation), May 15, 1981 (revision)
            1977 (publication)
            NaN-NaN-NaN (publication)

    :param date_str: 

    '''
    try:
        out = []
        for date in json.loads(date_str):
            value = toolkit.h.render_datetime(date[u'value']) or date[u'value']
            out.append(u'{0} ({1})'.format(value, date[u'type']))
        return u', '.join(out)
    except (ValueError, TypeError):
        return date_str


def get_responsible_party(value):
    '''Gets a responsible party extra created by the harvesters and formats it
        nicely for the UI.
    
        Examples:
            [{"name": "Complex Systems Research Center", "roles": ["pointOfContact"]}]
            [{"name": "British Geological Survey", "roles": ["custodian",
            "pointOfContact"]}, {"name": "Natural England", "roles": ["publisher"]}]
    
        Results
            Complex Systems Research Center (pointOfContact)
            British Geological Survey (custodian, pointOfContact); Natural England (
            publisher)

    :param value: 

    '''
    formatted = {
        u'resourceProvider': toolkit._(u'Resource Provider'),
        u'pointOfContact': toolkit._(u'Point of Contact'),
        u'principalInvestigator': toolkit._(u'Principal Investigator'),
        }

    try:
        out = []
        parties = toolkit.h.json.loads(value)
        for party in parties:
            roles = [formatted[role] if role in formatted.keys() else toolkit._(
                role.capitalize()) for role in party[u'roles']]
            out.append(u'{0} ({1})'.format(party[u'name'], u', '.join(roles)))
        return u'; '.join(out)
    except (ValueError, TypeError):
        return value


def get_common_map_config():
    '''Returns a dict with all configuration options related to the common
        base map (ie those starting with 'ckanext.spatial.common_map.')


    '''
    namespace = u'ckanext.spatial.common_map.'
    return dict([(k.replace(namespace, u''), v) for k, v in toolkit.config.iteritems() if
                 k.startswith(namespace)])

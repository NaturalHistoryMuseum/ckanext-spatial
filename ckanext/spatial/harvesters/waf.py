#!/usr/bin/env python
# encoding: utf-8

import hashlib
import logging
from urlparse import urljoin

import dateutil.parser
import pyparsing as parse
import requests
from ckanext.harvest.interfaces import IHarvester
from ckanext.harvest.model import HarvestObject, HarvestObjectExtra as HOExtra
from ckanext.spatial.harvesters.base import SpatialHarvester, guess_standard
from sqlalchemy.orm import aliased

from ckan import model
from ckan.plugins import SingletonPlugin, implements

log = logging.getLogger(__name__)


class WAFHarvester(SpatialHarvester, SingletonPlugin):
    '''A Harvester for WAF (Web Accessible Folders) containing spatial metadata
    documents.
    e.g. Apache serving a directory of ISO 19139 files.


    '''

    implements(IHarvester)

    def info(self):
        ''' '''
        return {
            u'name': u'waf',
            u'title': u'Web Accessible Folder (WAF)',
            u'description': u'A Web Accessible Folder (WAF) displaying a list of '
                            u'spatial metadata documents'
            }

    def get_original_url(self, harvest_object_id):
        '''

        :param harvest_object_id: 

        '''
        url = model.Session.query(HOExtra.value).filter(
            HOExtra.key == u'waf_location').filter(
            HOExtra.harvest_object_id == harvest_object_id).first()

        return url[0] if url else None

    def gather_stage(self, harvest_job, collection_package_id=None):
        '''

        :param harvest_job: 
        :param collection_package_id:  (Default value = None)

        '''
        log = logging.getLogger(__name__ + u'.WAF.gather')
        log.debug(u'WafHarvester gather_stage for job: %r', harvest_job)

        self.harvest_job = harvest_job

        # Get source URL
        source_url = harvest_job.source.url

        self._set_source_config(harvest_job.source.config)

        # Get contents
        try:
            response = requests.get(source_url, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException, e:
            self._save_gather_error(
                u'Unable to get content for URL: %s: %r' % (source_url, e), harvest_job)
            return None

        content = response.content
        scraper = _get_scraper(response.headers.get(u'server'))

        ######  Get current harvest object out of db ######

        url_to_modified_db = {}  ## mapping of url to last_modified in db
        url_to_ids = {}  ## mapping of url to guid in db

        HOExtraAlias1 = aliased(HOExtra)
        HOExtraAlias2 = aliased(HOExtra)
        query = model.Session.query(HarvestObject.guid, HarvestObject.package_id,
                                    HOExtraAlias1.value, HOExtraAlias2.value).join(
            HOExtraAlias1, HarvestObject.extras).join(HOExtraAlias2,
                                                      HarvestObject.extras).filter(
            HOExtraAlias1.key == u'waf_modified_date').filter(
            HOExtraAlias2.key == u'waf_location').filter(
            HarvestObject.current == True).filter(
            HarvestObject.harvest_source_id == harvest_job.source.id)

        for guid, package_id, modified_date, url in query:
            url_to_modified_db[url] = modified_date
            url_to_ids[url] = (guid, package_id)

        ######  Get current list of records from source ######

        url_to_modified_harvest = {}  ## mapping of url to last_modified in harvest
        try:
            for url, modified_date in _extract_waf(content, source_url, scraper):
                url_to_modified_harvest[url] = modified_date
        except Exception, e:
            msg = u'Error extracting URLs from %s, error was %s' % (source_url, e)
            self._save_gather_error(msg, harvest_job)
            return None

        ######  Compare source and db ######

        harvest_locations = set(url_to_modified_harvest.keys())
        old_locations = set(url_to_modified_db.keys())

        new = harvest_locations - old_locations
        delete = old_locations - harvest_locations
        possible_changes = old_locations & harvest_locations
        change = []

        for item in possible_changes:
            if (not url_to_modified_harvest[item] or not url_to_modified_db[item]  #
                    # if there is no date assume change
                    or url_to_modified_harvest[item] > url_to_modified_db[item]):
                change.append(item)

        def create_extras(url, date, status):
            '''

            :param url: 
            :param date: 
            :param status: 

            '''
            extras = [HOExtra(key=u'waf_modified_date', value=date),
                      HOExtra(key=u'waf_location', value=url),
                      HOExtra(key=u'status', value=status)]
            if collection_package_id:
                extras.append(
                    HOExtra(key=u'collection_package_id',
                            value=collection_package_id)
                    )
            return extras

        ids = []
        for location in new:
            guid = hashlib.md5(location.encode(u'utf8', u'ignore')).hexdigest()
            obj = HarvestObject(job=harvest_job,
                                extras=create_extras(location,
                                                     url_to_modified_harvest[location],
                                                     u'new'),
                                guid=guid
                                )
            obj.save()
            ids.append(obj.id)

        for location in change:
            obj = HarvestObject(job=harvest_job,
                                extras=create_extras(location,
                                                     url_to_modified_harvest[location],
                                                     u'change'),
                                guid=url_to_ids[location][0],
                                package_id=url_to_ids[location][1],
                                )
            obj.save()
            ids.append(obj.id)

        for location in delete:
            obj = HarvestObject(job=harvest_job,
                                extras=create_extras(u'', u'', u'delete'),
                                guid=url_to_ids[location][0],
                                package_id=url_to_ids[location][1],
                                )
            model.Session.query(HarvestObject).filter_by(
                guid=url_to_ids[location][0]).update({
                u'current': False
                }, False)

            obj.save()
            ids.append(obj.id)

        if len(ids) > 0:
            log.debug(
                u'{0} objects sent to the next stage: {1} new, {2} change, '
                u'{3} delete'.format(
                    len(ids), len(new), len(change), len(delete)))
            return ids
        else:
            self._save_gather_error(u'No records to change',
                                    harvest_job)
            return []

    def fetch_stage(self, harvest_object):
        '''

        :param harvest_object: 

        '''

        # Check harvest object status
        status = self._get_object_extra(harvest_object, u'status')

        if status == u'delete':
            # No need to fetch anything, just pass to the import stage
            return True

        # We need to fetch the remote document

        # Get location
        url = self._get_object_extra(harvest_object, u'waf_location')
        if not url:
            self._save_object_error(
                u'No location defined for object {0}'.format(harvest_object.id),
                harvest_object)
            return False

        # Get contents
        try:
            content = self._get_content_as_unicode(url)
        except Exception, e:
            msg = u'Could not harvest WAF link {0}: {1}'.format(url, e)
            self._save_object_error(msg, harvest_object)
            return False

        # Check if it is an ISO document
        document_format = guess_standard(content)
        if document_format == u'iso':
            harvest_object.content = content
            harvest_object.save()
        else:
            extra = HOExtra(
                object=harvest_object,
                key=u'original_document',
                value=content)
            extra.save()

            extra = HOExtra(
                object=harvest_object,
                key=u'original_format',
                value=document_format)
            extra.save()

        return True


apache = parse.SkipTo(parse.CaselessLiteral(u'<a href='),
                      include=True).suppress() + parse.quotedString.setParseAction(
    parse.removeQuotes).setResultsName(u'url') + parse.SkipTo(u'</a>',
                                                              include=True).suppress()\
         + parse.Optional(
    parse.Literal(u'</td><td align="right">')).suppress() + parse.Optional(parse.Combine(
    parse.Word(parse.alphanums + u'-') +
    parse.Word(parse.alphanums + u':')
    , adjacent=False, joinString=u' ').setResultsName(u'date')
                                                                           )

iis = parse.SkipTo(u'<br>').suppress() + parse.OneOrMore(
    u'<br>').suppress() + parse.Optional(parse.Combine(
    parse.Word(parse.alphanums + '/') +
    parse.Word(parse.alphanums + u':') +
    parse.Word(parse.alphas)
    , adjacent=False, joinString=u' ').setResultsName(u'date')
                                         ) + parse.Word(
    parse.nums).suppress() + parse.Literal(
    u'<A HREF=').suppress() + parse.quotedString.setParseAction(
    parse.removeQuotes).setResultsName(u'url')

other = parse.SkipTo(parse.CaselessLiteral(u'<a href='),
                     include=True).suppress() + parse.quotedString.setParseAction(
    parse.removeQuotes).setResultsName(u'url')

scrapers = {
    u'apache': parse.OneOrMore(parse.Group(apache)),
    u'other': parse.OneOrMore(parse.Group(other)),
    u'iis': parse.OneOrMore(parse.Group(iis))
    }


def _get_scraper(server):
    '''

    :param server: 

    '''
    if not server or u'apache' in server.lower():
        return u'apache'
    if server == u'Microsoft-IIS/7.5':
        return u'iis'
    else:
        return u'other'


def _extract_waf(content, base_url, scraper, results=None, depth=0):
    '''

    :param content: 
    :param base_url: 
    :param scraper: 
    :param results:  (Default value = None)
    :param depth:  (Default value = 0)

    '''
    if results is None:
        results = []

    base_url = base_url.rstrip('/').split('/')
    if u'index' in base_url[-1]:
        base_url.pop()
    base_url = '/'.join(base_url)
    base_url += '/'

    try:
        parsed = scrapers[scraper].parseString(content)
    except parse.ParseException:
        parsed = scrapers[u'other'].parseString(content)

    for record in parsed:
        url = record.url
        if not url:
            continue
        if url.startswith(u'_'):
            continue
        if u'?' in url:
            continue
        if u'#' in url:
            continue
        if u'mailto:' in url:
            continue
        if u'..' not in url and url[0] != '/' and url[-1] == '/':
            new_depth = depth + 1
            if depth > 10:
                log.info(u'Max WAF depth reached')
                continue
            new_url = urljoin(base_url, url)
            if not new_url.startswith(base_url):
                continue
            log.debug(u'WAF new_url: %s', new_url)
            try:
                response = requests.get(new_url)
                content = response.content
            except Exception, e:
                print str(e)
                continue
            _extract_waf(content, new_url, scraper, results, new_depth)
            continue
        if not url.endswith(u'.xml'):
            continue
        date = record.date
        if date:
            try:
                date = str(dateutil.parser.parse(date))
            except Exception, e:
                raise
                date = None
        results.append((urljoin(base_url, record.url), date))

    return results

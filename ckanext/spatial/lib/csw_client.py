# !/usr/bin/env python
# encoding: utf-8

import logging

from owslib.etree import etree
from owslib.fes import PropertyIsEqualTo, SortBy, SortProperty

log = logging.getLogger(__name__)


class CswError(Exception):
    ''' '''
    pass


class OwsService(object):
    ''' '''

    def __init__(self, endpoint=None):
        if endpoint is not None:
            self._ows(endpoint)

    def __call__(self, args):
        return getattr(self, args.operation)(**self._xmd(args))

    @classmethod
    def _operations(cls):
        ''' '''
        return [x for x in dir(cls) if not x.startswith(u'_')]

    def _xmd(self, obj):
        '''

        :param obj: 

        '''
        md = {}
        for attr in [x for x in dir(obj) if not x.startswith(u'_')]:
            val = getattr(obj, attr)
            if not val:
                pass
            elif callable(val):
                pass
            elif isinstance(val, basestring):
                md[attr] = val
            elif isinstance(val, int):
                md[attr] = val
            elif isinstance(val, list):
                md[attr] = val
            else:
                md[attr] = self._xmd(val)
        return md

    def _ows(self, endpoint=None, **kw):
        '''

        :param endpoint:  (Default value = None)
        :param **kw: 

        '''
        if not hasattr(self, u'_Implementation'):
            raise NotImplementedError(u'Needs an Implementation')
        if not hasattr(self, u'__ows_obj__'):
            if endpoint is None:
                raise ValueError(u'Must specify a service endpoint')
            self.__ows_obj__ = self._Implementation(endpoint)
        return self.__ows_obj__

    def getcapabilities(self, debug=False, **kw):
        '''

        :param debug:  (Default value = False)
        :param **kw: 

        '''
        ows = self._ows(**kw)
        caps = self._xmd(ows)
        if not debug:
            if u'request' in caps:
                del caps[u'request']
            if u'response' in caps:
                del caps[u'response']
        if u'owscommon' in caps:
            del caps[u'owscommon']
        return caps


class CswService(OwsService):
    '''Perform various operations on a CSW service'''

    def __init__(self, endpoint=None):
        super(CswService, self).__init__(endpoint)
        self.sortby = SortBy([SortProperty(u'dc:identifier')])

    def getrecords(self, qtype=None, keywords=[],
                   typenames=u'csw:Record', esn=u'brief',
                   skip=0, count=10, outputschema=u'gmd', **kw):
        '''

        :param qtype:  (Default value = None)
        :param keywords:  (Default value = [])
        :param typenames:  (Default value = u'csw:Record')
        :param esn:  (Default value = u'brief')
        :param skip:  (Default value = 0)
        :param count:  (Default value = 10)
        :param outputschema:  (Default value = u'gmd')
        :param **kw: 

        '''
        from owslib.csw import namespaces
        constraints = []
        csw = self._ows(**kw)

        if qtype is not None:
            constraints.append(PropertyIsEqualTo(u'dc:type', qtype))

        kwa = {
            u'constraints': constraints,
            u'typenames': typenames,
            u'esn': esn,
            u'startposition': skip,
            u'maxrecords': count,
            u'outputschema': namespaces[outputschema],
            u'sortby': self.sortby
            }
        log.info(u'Making CSW request: getrecords2 %r', kwa)
        csw.getrecords2(**kwa)
        if csw.exceptionreport:
            err = u'Error getting records: %r' % \
                  csw.exceptionreport.exceptions
            # log.error(err)
            raise CswError(err)
        return [self._xmd(r) for r in csw.records.values()]

    def getidentifiers(self, qtype=None, typenames=u'csw:Record', esn=u'brief',
                       keywords=[], limit=None, page=10, outputschema=u'gmd',
                       startposition=0, cql=None, **kw):
        '''

        :param qtype:  (Default value = None)
        :param typenames:  (Default value = u'csw:Record')
        :param esn:  (Default value = u'brief')
        :param keywords:  (Default value = [])
        :param limit:  (Default value = None)
        :param page:  (Default value = 10)
        :param outputschema:  (Default value = u'gmd')
        :param startposition:  (Default value = 0)
        :param cql:  (Default value = None)
        :param **kw: 

        '''
        from owslib.csw import namespaces
        constraints = []
        csw = self._ows(**kw)

        if qtype is not None:
            constraints.append(PropertyIsEqualTo(u'dc:type', qtype))

        kwa = {
            u'constraints': constraints,
            u'typenames': typenames,
            u'esn': esn,
            u'startposition': startposition,
            u'maxrecords': page,
            u'outputschema': namespaces[outputschema],
            u'cql': cql,
            u'sortby': self.sortby
            }
        i = 0
        matches = 0
        while True:
            log.info(u'Making CSW request: getrecords2 %r', kwa)

            csw.getrecords2(**kwa)
            if csw.exceptionreport:
                err = u'Error getting identifiers: %r' % \
                      csw.exceptionreport.exceptions
                # log.error(err)
                raise CswError(err)

            if matches == 0:
                matches = csw.results[u'matches']

            identifiers = csw.records.keys()
            if limit is not None:
                identifiers = identifiers[:(limit - startposition)]
            for ident in identifiers:
                yield ident

            if len(identifiers) == 0:
                break

            i += len(identifiers)
            if limit is not None and i > limit:
                break

            startposition += page
            if startposition >= (matches + 1):
                break

            kwa[u'startposition'] = startposition

    def getrecordbyid(self, ids=[], esn=u'full', outputschema=u'gmd', **kw):
        '''

        :param ids:  (Default value = [])
        :param esn:  (Default value = u'full')
        :param outputschema:  (Default value = u'gmd')
        :param **kw: 

        '''
        from owslib.csw import namespaces
        csw = self._ows(**kw)
        kwa = {
            u'esn': esn,
            u'outputschema': namespaces[outputschema],
            }
        # Ordinary Python version's don't support the metadata argument
        log.info(u'Making CSW request: getrecordbyid %r %r', ids, kwa)
        csw.getrecordbyid(ids, **kwa)
        if csw.exceptionreport:
            err = u'Error getting record by id: %r' % \
                  csw.exceptionreport.exceptions
            # log.error(err)
            raise CswError(err)
        if not csw.records:
            return
        record = self._xmd(csw.records.values()[0])

        ## strip off the enclosing results container, we only want the metadata
        # md = csw._exml.find("/gmd:MD_Metadata")#, namespaces=namespaces)
        # Ordinary Python version's don't support the metadata argument
        md = csw._exml.find('/{http://www.isotc211.org/2005/gmd}MD_Metadata')
        mdtree = etree.ElementTree(md)
        try:
            record[u'xml'] = etree.tostring(mdtree, pretty_print=True, encoding=unicode)
        except TypeError:
            # API incompatibilities between different flavours of elementtree
            try:
                record[u'xml'] = etree.tostring(mdtree, pretty_print=True,
                                                encoding=unicode)
            except AssertionError:
                record[u'xml'] = etree.tostring(md, pretty_print=True, encoding=unicode)

        record[u'xml'] = u'<?xml version="1.0" encoding="UTF-8"?>\n' + record[u'xml']
        record[u'tree'] = mdtree
        return record

# !/usr/bin/env python
# encoding: utf-8

import csv
import datetime
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class ReportTable(object):
    ''' '''

    def __init__(self, column_names):
        assert isinstance(column_names, (list, tuple))
        self.column_names = column_names
        self.rows = []

    def add_row_dict(self, row_dict):
        '''Adds a row to the report table

        :param row_dict: 

        '''
        row = []
        for col_name in self.column_names:
            if col_name in row_dict:
                value = row_dict.pop(col_name)
            else:
                value = None
            row.append(value)
        if row_dict:
            raise Exception(u'Have left-over keys not under a column: %s' % row_dict)
        self.rows.append(row)

    def get_rows_html_formatted(self, date_format=u'%d/%m/%y %H:%M',
                                blank_cell_html=u''):
        '''

        :param date_format:  (Default value = u'%d/%m/%y %H:%M')
        :param blank_cell_html:  (Default value = u'')

        '''
        for row in self.rows:
            row_formatted = row[:]
            for i, cell in enumerate(row):
                if isinstance(cell, datetime.datetime):
                    row_formatted[i] = cell.strftime(date_format)
                elif cell is None:
                    row_formatted[i] = blank_cell_html
            yield row_formatted

    def get_csv(self):
        ''' '''
        csvout = StringIO()
        csvwriter = csv.writer(
            csvout,
            dialect=u'excel',
            quoting=csv.QUOTE_NONNUMERIC
            )
        csvwriter.writerow(self.column_names)
        for row in self.rows:
            row_formatted = []
            for cell in row:
                if isinstance(cell, datetime.datetime):
                    cell = cell.strftime(u'%Y-%m-%d %H:%M')
                elif isinstance(cell, (int, long)):
                    cell = str(cell)
                elif isinstance(cell, (list, tuple)):
                    cell = str(cell)
                elif cell is None:
                    cell = u''
                else:
                    cell = cell.encode(u'utf8')
                row_formatted.append(cell)
            try:
                csvwriter.writerow(row_formatted)
            except Exception, e:
                raise Exception(u'%s: %s, %s' % (e, row, row_formatted))
        csvout.seek(0)
        return csvout.read()

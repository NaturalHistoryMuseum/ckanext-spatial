#!/usr/bin/env python
# encoding: utf-8

import SimpleHTTPServer
import SocketServer
from threading import Thread

import os

PORT = 8999


def serve(port=PORT):
    '''Serves test XML files over HTTP

    :param port:  (Default value = PORT)

    '''

    # Make sure we serve from the tests' XML directory
    os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          u'xml'))

    Handler = SimpleHTTPServer.SimpleHTTPRequestHandler

    class TestServer(SocketServer.TCPServer):
        ''' '''
        allow_reuse_address = True

    httpd = TestServer((u'', PORT), Handler)

    print u'Serving test HTTP server at port', PORT

    httpd_thread = Thread(target=httpd.serve_forever)
    httpd_thread.setDaemon(True)
    httpd_thread.start()

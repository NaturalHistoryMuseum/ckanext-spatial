#!/usr/bin/env python
# encoding: utf-8

try:
    import pkg_resources
    pkg_resources.declare_namespace(__name__)
except ImportError:
    import pkgutil
    __path__ = pkgutil.extend_path(__path__, __name__)

from package_extent import *
from harvested_metadata import *

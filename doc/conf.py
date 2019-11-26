
#!/usr/bin/env python
# encoding: utf-8

import sys, os




extensions = [u'sphinx.ext.autodoc', u'sphinx.ext.todo', u'sphinx.ext.intersphinx']

templates_path = [u'_templates']

source_suffix = u'.rst'


master_doc = u'index'

project = u'ckanext-spatial'
copyright = u'2015, Open Knowledge'

version = u'0.1'
release = u'0.1'



exclude_patterns = []





pygments_style = u'sphinx'



exclude_trees = [u'.build']



on_rtd = os.environ.get(u'READTHEDOCS', None) == u'True'
if not on_rtd:
    import sphinx_rtd_theme
    html_theme = u'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

#html_theme = 'default'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []
html_sidebars = {
    u'**':  [u'globaltoc.html']
}






html_static_path = [u'_static']













htmlhelp_basename = u'ckanext-spatialdoc'



latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

latex_documents = [
  (u'index', u'ckanext-spatial.tex', u'ckanext-spatial Documentation',
   u'Open Knowledge Foundation', u'manual'),
]









man_pages = [
    (u'index', u'ckanext-spatial', u'ckanext-spatial Documentation',
     [u'Open Knowledge Foundation'], 1)
]




texinfo_documents = [
  (u'index', u'ckanext-spatial', u'ckanext-spatial Documentation',
   u'Open Knowledge Foundation', u'ckanext-spatial', u'One line description of project.',
   u'Miscellaneous'),
]






intersphinx_mapping = {u'http://docs.python.org/': None}

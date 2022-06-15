# Licensed under a 3-clause BSD style license - see LICENSE.rst
from setuptools import setup

try:
    from testr.setup_helper import cmdclass
except ImportError:
    cmdclass = {}

setup(name='kadi-apps',
      author='Javier Gonzalez',
      description='Ska REST API',
      author_email='javier.gonzalez@cfa.harvard.edu',
      packages=['kadi_apps', 'kadi_apps.settings', 'kadi_apps.blueprints'],
      license=("New BSD/3-clause BSD License\nCopyright (c) 2021"
               " Smithsonian Astrophysical Observatory\nAll rights reserved."),
      url='http://github.com/sot/web-kadi-apps',
      use_scm_version=True,
      setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
      zip_safe=False,
      # tests_require=['pytest'],
      # package_data={'kadi_apps.tests': ['data/*.pkl']},
      cmdclass=cmdclass,
      )

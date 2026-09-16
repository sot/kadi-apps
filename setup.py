# Licensed under a 3-clause BSD style license - see LICENSE.rst
from setuptools import setup
from pathlib import Path

try:
    from testr.setup_helper import cmdclass
except ImportError:
    cmdclass = {}


entry_points = {
    "console_scripts": [
        "kadi-apps-test-server=kadi_apps.app:main",
        "kadi-apps=kadi_apps.scripts.kadi_apps_cmd:main",
    ]
}


def static_files():
    """
    Find all "static" directories, list their contents and match them to their
    destination directory. Returns a list [(dest, [file, ...]), ...].
    """
    root = Path(__file__).parent
    static_dest = Path('share') / 'kadi_apps' / 'static'
    data_files = {}
    all_files = [(s, p) for s in root.glob('**/static') for p in s.glob('**/*')]
    for s, p in all_files:
        if not p.is_file():
            continue
        dest = str((static_dest / p.relative_to(s)).parent)
        data_files[dest] = data_files.get(dest, []) + [str(p)]
    return list(data_files.items())


setup(
    name='kadi-apps',
    author='Javier Gonzalez',
    description='Kadi Web Apps',
    author_email='javier.gonzalez@cfa.harvard.edu',
    packages=[
        'kadi_apps',
        'kadi_apps.settings',
        'kadi_apps.scripts',
        'kadi_apps.scripts.kadi_apps_cmd',
        'kadi_apps.tests',
        'kadi_apps.blueprints',
        'kadi_apps.blueprints.ska_api',
        'kadi_apps.blueprints.find_attitude',
        'kadi_apps.blueprints.kadi',
        'kadi_apps.blueprints.mica',
        'kadi_apps.blueprints.pcad_acq',
        'kadi_apps.blueprints.star_hist',
    ],
    license=(
        "New BSD/3-clause BSD License\nCopyright (c) 2021"
        " Smithsonian Astrophysical Observatory\nAll rights reserved."
    ),
    url='http://github.com/sot/kadi-apps',
    use_scm_version=True,
    setup_requires=['setuptools_scm', 'setuptools_scm_git_archive'],
    zip_safe=False,
    # tests_require=['pytest'],
    package_data={
        'kadi_apps': ['environment.yml', 'templates/*.html', 'static/images/*'],
        'kadi_apps.scripts.kadi_apps_cmd': ['supervisord.conf', 'environment.yml'],
        'kadi_apps.tests': ['**/*'],
        'kadi_apps.blueprints.ska_api': ['templates/*.html'],
        'kadi_apps.blueprints.find_attitude': ['templates/find_attitude/*.html'],
        'kadi_apps.blueprints.kadi': ['templates/events/*.html'],
        'kadi_apps.blueprints.mica': ['templates/mica/*.html'],
        'kadi_apps.blueprints.pcad_acq': ['templates/pcad_table/*.html'],
        'kadi_apps.blueprints.star_hist': ['templates/star_hist/*.html'],
    },
    data_files=static_files(),
    entry_points=entry_points,
    cmdclass=cmdclass,
)

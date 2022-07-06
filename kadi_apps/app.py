#!/usr/bin/env python

"""
"""

import logging
import argparse

from pathlib import Path

from flask import Flask
from flask_cors import CORS
from kadi_apps.rendering import render_template

import pyyaks.logger


def page_not_found(e):
    return render_template('404.html'), 404


def internal_error(e):
    return render_template('500.html'), 500


def get_app(name=__name__, settings='devel'):
    import kadi_apps
    from kadi_apps.blueprints import auth, test, astromon, ska_api as api, kadi, find_attitude
    from kadi_apps.blueprints import mica, star_hist, pcad_acq

    logger = pyyaks.logger.get_logger(name='kadi_apps', level='INFO')
    msg = f'Starting Kadi Apps version {kadi_apps.__version__}'
    logger.info(f' {"-"*len(msg)}')
    logger.info(f' {msg}')
    logger.info(f' {"-"*len(msg)}')

    app = Flask(name, static_folder='static', template_folder='templates')

    CORS(app, supports_credentials=True)  # resources={r"*": {"origins": "http://kadi-dev:3000/*"}})

    settings = f'kadi_apps.settings.{settings}'
    logger.info(f'Loading Ska app settings from {settings}')
    app.config.from_object(settings)
    if 'KADI_APPS_CONFIG_DIR' in app.config:
        config_dir = Path(app.config['KADI_APPS_CONFIG_DIR'])
        assert config_dir.exists(), f'Config directory "{config_dir}" does not exist'
        for filename in config_dir.glob('*.py'):
            logging.warning(f'Loading Ska app settings from {filename}')
            app.config.from_pyfile(filename)

    pyyaks.logger.get_logger(name='kadi_apps', level=app.config['LOG_LEVEL'])

    app.register_error_handler(404, page_not_found)
    app.register_error_handler(500, internal_error)

    app.register_blueprint(kadi.blueprint, url_prefix='/')
    app.register_blueprint(find_attitude.blueprint, url_prefix='/find_attitude')
    app.register_blueprint(mica.blueprint, url_prefix='/mica')
    app.register_blueprint(star_hist.blueprint, url_prefix='/star_hist')
    app.register_blueprint(pcad_acq.blueprint, url_prefix='/pcad_acq')

    app.register_blueprint(auth.blueprint, url_prefix='/api/auth')
    app.register_blueprint(test.blueprint, url_prefix='/api/test')
    app.register_blueprint(api.blueprint, url_prefix='/api/ska_api')
    app.register_blueprint(astromon.blueprint, url_prefix='/api/astromon')

    return app


def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unit-test', action='store_const', const='unit_test', dest='settings', default='devel')
    return parser


def main():
    # this starts the development server
    args = get_parser().parse_args()
    get_app(settings=args.settings).run(host='0.0.0.0')


if __name__ == "__main__":
    main()

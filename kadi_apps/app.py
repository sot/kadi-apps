#!/usr/bin/env python

"""
"""

import logging
import argparse

from pathlib import Path

from flask import Flask
from flask_cors import CORS

import pyyaks.logger


def get_app(name=__name__, settings='devel'):
    import kadi_apps
    from kadi_apps.blueprints import auth, test, astromon, ska_api as api

    logger = pyyaks.logger.get_logger(name='kadi_apps', level='INFO')
    msg = f'Starting Ska API version {kadi_apps.__version__}'
    logger.info(f' {"-"*len(msg)}')
    logger.info(f' {msg}')
    logger.info(f' {"-"*len(msg)}')
    app = Flask(name)

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

    app.register_blueprint(auth.blueprint, url_prefix='/auth')
    app.register_blueprint(test.blueprint, url_prefix='/test')
    app.register_blueprint(astromon.blueprint, url_prefix='/astromon')
    app.register_blueprint(api.blueprint, url_prefix='/ska_api')

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

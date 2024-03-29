#!/usr/bin/env python

"""
"""

import logging
import argparse
import os
import dotenv

from pathlib import Path

from flask import Flask
from flask_cors import CORS
from kadi_apps.rendering import render_template

import pyyaks.logger


def page_not_found(e):
    return render_template('404.html'), 404


def internal_error(e):
    return render_template('500.html'), 500


def index():
    """Return main page"""
    return render_template(
        'index.html',
    )


def api_index():
    """Return main API page"""
    return render_template(
        'api_index.html',
    )


def get_app(name=__name__, settings='devel'):
    import kadi_apps
    from kadi_apps.blueprints import auth, test, ska_api as api, kadi, find_attitude
    from kadi_apps.blueprints import mica, star_hist, pcad_acq, astromon

    logger = pyyaks.logger.get_logger(name='kadi_apps', level='INFO')
    msg = f'Starting Kadi Apps version {kadi_apps.__version__}'
    logger.info(f' {"-"*len(msg)}')
    logger.info(f' {msg}')
    logger.info(f' {"-"*len(msg)}')

    app = Flask(name, static_folder='static', template_folder='templates')

    CORS(app, supports_credentials=True)  # resources={r"*": {"origins": "http://kadi-dev:3000/*"}})

    dotenv_file = Path(f'.env_{settings}')
    settings = f'kadi_apps.settings.{settings}'
    if dotenv_file.exists():
        logger.info(f"loading {dotenv_file.absolute()}")
        dotenv.load_dotenv(dotenv_file)
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

    app.add_url_rule("/", view_func=index)
    app.add_url_rule("/api/", view_func=api_index)

    app.register_blueprint(kadi.blueprint, url_prefix='/kadi')
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
    parser.add_argument('--ssl', action='store_const', const='adhoc', default=None)
    return parser


def main():
    # this starts the development server
    args = get_parser().parse_args()
    app = get_app(settings=args.settings)
    app.run(host='0.0.0.0', port=app.config['PORT'], ssl_context=args.ssl)


if __name__ == "__main__":
    main()


"""
This implements Github's oauth flow.

The authentication flow in python:

    import requests
    import json
    url_prefix = https://web-kadi-test.cfa.harvard.edu/ska  # change accordingly
    r = requests.get(f'{url_prefix}/authorization_url')
    r = json.loads(r.content.decode())
    r['authorization_url'] # take the browser here

you will be redirected to a URL that looks like:

    authorization_url = 'https://example.com/auth?code=<code>&state=<token>'

and note that this URL contains a 'state' variable and a 'code' variable. The state variable should
match the one in r['state']. now do:
    r = requests.post(f'{url_prefix}/token', json={'authorization_response': authorization_url})
or
    r = requests.post(f'{url_prefix}/token', json={'code': code})
    r = json.loads(r.content.decode())

"""

import logging

from flask import Blueprint
from flask_restful import reqparse
from flask import current_app

from requests_oauthlib import OAuth2Session


logger = logging.getLogger('ska_api')


AUTH_BASE_URL = 'https://github.com/login/oauth/authorize'
TOKEN_URL = 'https://github.com/login/oauth/access_token'


blueprint = Blueprint('github_oauth', __name__)


@blueprint.route('/')
def auth():
    """
    Authorize with Github.

    This function returns a dictionary with two entries. The browser should be redirected to
    authorization_url so the user authorizes the use of the Github account. After the user
    authorizes, the browser is redirected to another URL (which is set in the OAuth app settings
    in Github, setting two URL arguments: code, and state.
    """
    try:
        assert 'CLIENT_ID' in current_app.config, 'CLIENT_ID is not present in config'
        logger.info('Authorizing with Github')
        github = OAuth2Session(
            current_app.config['CLIENT_ID']
        )
        authorization_url, state = github.authorization_url(AUTH_BASE_URL)
    except Exception as e:
        logger.error(f'Exception in Auth.get: {e}')
        return {}, 500
    return {'authorization_url': authorization_url, 'state': state}, 200


@blueprint.route('/token', methods=['GET', 'POST'])
def token():
    """
    """
    try:
        assert 'CLIENT_ID' in current_app.config, 'CLIENT_ID is not present in config'
        assert 'CLIENT_SECRET' in current_app.config, 'CLIENT_SECRET is not present in config'
        res = {}
        logger.info('Getting token')
        github = OAuth2Session(
            current_app.config['CLIENT_ID']
        )
        parse = reqparse.RequestParser()
        parse.add_argument('authorization_response')
        parse.add_argument('code')
        parse.add_argument('state')
        args = parse.parse_args()
        if args.code is not None:
            logger.info('with code')
        if args.authorization_response is not None:
            logger.info('with authorization_response')
        if not (args.authorization_response is not None or args.code is not None):
            raise ValueError('Need to provide authorization_response or code')
        res = github.fetch_token(
            TOKEN_URL,
            client_secret=current_app.config['CLIENT_SECRET'],
            authorization_response=args.authorization_response,
            code=args.code
        )
    except Exception as e:
        logger.error(f'Exception ({type(e).__name__}) in Auth.post: {e}')
        return {}, 500
    return res, 200

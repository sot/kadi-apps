import logging
import jwt
import datetime
import json

from flask import Blueprint, request
from flask_restful import reqparse
from flask import current_app, after_this_request
from werkzeug.security import check_password_hash


from ska_api.authentication import generate_token


blueprint = Blueprint('auth', __name__)


def _check_password(user, password):
    with open(current_app.config['PASSWORDS']) as fh:
        users = json.load(fh)
        if user in users:
            return check_password_hash(users[user], password)
    return False


def _check_token(token):
    try:
        data = jwt.decode(token, current_app.config['JWT_SECRET'], algorithms="HS256")
        if tuple(data['version']) >= current_app.config['TOKEN_VERSION']:
            return data
    except Exception as e:
        print(e)
    return {}


@blueprint.route('/token', methods=['POST'])
def token():
    logging.getLogger('ska_api').info('Getting token')

    parse = reqparse.RequestParser()
    parse.add_argument('user')
    parse.add_argument('password')
    args = parse.parse_args()

    cookie = request.cookies.get('refresh_token')
    refresh_token_payload = _check_token(cookie)
    cookie_is_valid = cookie is not None and refresh_token_payload

    ok = bool(cookie_is_valid) | _check_password(args.user, args.password)
    if not ok:
        return {'ok': False, 'message': '403 (forbidden)'}, 403
    user = refresh_token_payload['user'] if refresh_token_payload else args.user

    encoded_jwt = generate_token(
        user, current_app.config['JWT_SECRET'], validity=datetime.timedelta(minutes=10)
    )

    if not cookie_is_valid:
        refresh_token = generate_token(user, current_app.config['JWT_SECRET'])

        @after_this_request
        def set_cookie(response):
            response.set_cookie(
                'refresh_token',
                refresh_token,
                httponly=True,
                secure=True
            )
            return response

    return {'ok': True, 'token': encoded_jwt.decode()}, 200


@blueprint.route('/logout', methods=['POST'])
def logout():
    logging.getLogger('ska_api').info('Logging out')

    @after_this_request
    def delete_cookie(response):
        response.set_cookie(
            'refresh_token',
            'none',
            httponly=True,
            secure=True
        )
        return response
    return {'ok': True}, 200

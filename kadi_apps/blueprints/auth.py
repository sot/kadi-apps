import logging
import jwt
import datetime
import json

from flask import Blueprint, request
from flask import current_app, after_this_request
from werkzeug.security import check_password_hash


from kadi_apps.authentication import generate_token


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
        print(f"Error checking token: {e}")
    return {}


@blueprint.route('/token', methods=['POST'])
def token():
    logging.getLogger('kadi_apps').info('Getting token')

    try:
        args = request.get_json()
    except:
        args = {}
    user = args.get('user', None)
    password = args.get('password', None)
    cookie = request.cookies.get('refresh_token')
    refresh_token_payload = _check_token(cookie) if cookie else {}
    cookie_is_valid = bool(cookie is not None and refresh_token_payload)

    ok = cookie_is_valid
    if user is not None and password is not None:
        ok |= _check_password(user, password)
    if not ok:
        return {'ok': False, 'message': '403 (forbidden)'}, 403
    user = refresh_token_payload['user'] if refresh_token_payload else user

    token_validity = datetime.timedelta(minutes=10)
    token = generate_token(
        user, current_app.config['JWT_SECRET'], validity=token_validity
    )

    expiring_refresh_token = 'exp' not in refresh_token_payload
    if refresh_token_payload and not expiring_refresh_token:
        dt = datetime.datetime.fromtimestamp(refresh_token_payload['exp']) - datetime.datetime.utcnow()
        if dt > datetime.timedelta() and dt < datetime.timedelta(30):
            # refresh token has only 30 days left,
            # so it will be automatically refreshed.
            expiring_refresh_token = True
    if expiring_refresh_token or not cookie_is_valid:
        refresh_token = generate_token(
            user,
            current_app.config['JWT_SECRET'],
            validity=datetime.timedelta(days=365)
        )

        @after_this_request
        def set_cookie(response):
            response.set_cookie(
                'refresh_token',
                refresh_token,
                httponly=True,
                secure=True
            )
            return response

    return {
        'ok': True,
        'access_token': token,
        'token_type': 'bearer',
        'expires_in': token_validity.seconds,
    }, 200


@blueprint.route('/logout', methods=['POST'])
def logout():
    logging.getLogger('kadi_apps').info('Logging out')

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

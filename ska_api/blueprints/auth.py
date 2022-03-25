import logging
import jwt
import datetime
import json

from flask import Blueprint
from flask_restful import reqparse
from flask import current_app, after_this_request
from werkzeug.security import check_password_hash
# from werkzeug.security import generate_password_hash

blueprint = Blueprint('auth', __name__)


@blueprint.route('/test', methods=['POST'])
def root():
    logging.getLogger('ska_api').info('Getting auth.root')
    return {'token': 'the token'}, 200


@blueprint.route('/token', methods=['POST'])
def token():
    logging.getLogger('ska_api').info('Getting token')

    parse = reqparse.RequestParser()
    parse.add_argument('user')
    parse.add_argument('password')
    args = parse.parse_args()

    # cookies = dict(request.cookies)
    @after_this_request
    def set_is_bar_cookie(response):
        response.set_cookie('is_bar', 'no', max_age=64800, httponly=True)
        response.set_cookie('is_foo', 'no', max_age=64800, httponly=False)
        return response

    ok = False
    with open(current_app.config['PASSWORDS']) as fh:
        users = json.load(fh)
        if args.user in users:
            ok |= check_password_hash(users[args.user], args.password)
    if not ok:
        return {'ok': False, 'message': '403 (forbidden)'}, 403
    payload = {
        'user': args.user,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }

    encoded_jwt = jwt.encode(
        payload,
        current_app.config['JWT_SECRET'],
        algorithm="HS256"
    )

    return {'ok': True, 'token': encoded_jwt.decode()}, 200

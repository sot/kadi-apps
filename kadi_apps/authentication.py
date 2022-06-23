import datetime
import jwt
from functools import wraps
from flask import request, make_response, g, Response, current_app  # noqa
# from werkzeug.datastructures import Authorization


# flask-httpauth handles some authentication schemes (https://flask-httpauth.readthedocs.io)
# but I am trying different things and wanted a bare-bones approach.
# The interface is intended to be similar, though.

class Authentication:
    def __init__(self):
        self.user = None

    def authenticate(self):
        try:
            assert 'Authorization' in request.headers, 'a valid token is missing'
            token = request.headers['Authorization'].split()[-1]
            if token == 'null':  # this is the javascript "null" to which the token is initialized
                {'ok': False, 'message': 'Token is null'}
            data = decode_token(token)
            if not data:
                raise Exception('Token version is not valid')
            self.user = data['user']
        except Exception as e:
            self.user = None
            return {'ok': False, 'message': f'{type(e).__name__}, {e}'}
        return {'ok': True, 'message': ''}

    def login_required(self, f, ):
        @wraps(f)
        def decorated(*args, **kwargs):
            # auth = self.get_auth()
            authenticated = self.authenticate()

            if not authenticated['ok']:
                request.data  # # Clear TCP receive buffer of any pending data
                print(authenticated['message'])
                return {
                    'ok': False,
                    'message': f'Failed authentication: {authenticated["message"]}',
                }, 401

            return f(*args, **kwargs)
        return decorated


def password_hash(password):
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)


def parse_token_version(v):
    print('parsing', v)
    return tuple([int(i) for i in v.split('.')])


def generate_token(user, secret, validity=None):
    payload = {
        'user': user,
        'version': (1, 0),
    }
    if validity is not None:
        payload['exp'] = datetime.datetime.utcnow() + validity
    encoded_jwt = jwt.encode(
        payload,
        secret,
        algorithm="HS256"
    )
    return encoded_jwt


def decode_token(token):
    try:
        data = jwt.decode(token, current_app.config['JWT_SECRET'], algorithms="HS256")
        if tuple(data['version']) >= current_app.config['TOKEN_VERSION']:
            return data
    except Exception:
        pass
    return {}

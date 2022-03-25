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
            data = jwt.decode(token, current_app.config['JWT_SECRET'])
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

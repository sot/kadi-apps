from flask import Blueprint
from ska_api.authentication import Authentication


blueprint = Blueprint('private', __name__)


auth = Authentication()


@blueprint.route('/', methods=['GET'])
@auth.login_required
def token():
    return {'message': 'all ok', 'user': auth.user}, 200

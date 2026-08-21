import django.db

from kadi_apps.app import get_app


def test_django_connection_closed_after_request():
    app = get_app(settings='unit_test')
    with app.test_client() as client:
        response = client.get('/kadi/events/manvr/list/')
        assert response.status_code == 200
    # this is the main test: connections are closed after the request is done
    assert django.db.connections['default'].connection is None

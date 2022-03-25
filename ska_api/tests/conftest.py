import pytest
import time


def _run_app():
    import ska_api.app
    app = ska_api.app.get_app(settings='unit_test')
    app.run(host='0.0.0.0', debug=False)


@pytest.fixture(scope="session")
def test_server(request):
    print('ska_api.tests.conftest Starting Flask App')
    from multiprocessing import Process
    p = Process(target=_run_app)
    p.start()
    time.sleep(1)  # this is to let the server spin up
    info = {
        'url': 'http://127.0.0.1:5000',
        'user': 'test_user',
        'password': 'test_password',
    }
    yield info
    print('ska_api.tests.conftest Killing Flask App')
    p.kill()
    print('ska_api.tests.conftest done')

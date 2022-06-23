import pytest
import time


def _run_app():
    import kadi_apps.app
    app = kadi_apps.app.get_app(settings='unit_test')
    app.run(host='0.0.0.0', debug=False)


@pytest.fixture(scope="session")
def test_server(request):
    print('kadi_apps.tests.conftest Starting Flask App')
    from multiprocessing import Process
    p = Process(target=_run_app)
    p.start()
    time.sleep(2)  # this is to let the server spin up
    info = {
        'url': 'http://127.0.0.1:5000',
        'user': 'test_user',
        'password': 'test_password',
    }
    yield info
    print('kadi_apps.tests.conftest Killing Flask App')
    p.kill()
    print('kadi_apps.tests.conftest done')

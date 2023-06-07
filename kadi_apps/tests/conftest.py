import pytest
import time
import traceback


def _run_app():
    import kadi_apps.app
    app = kadi_apps.app.get_app(settings='unit_test')
    app.run(host='0.0.0.0', debug=False, port=app.config['PORT'])


@pytest.fixture(scope="session")
def test_server(request):
    import requests
    from kadi_apps.settings.unit_test import PORT
    from multiprocessing import Process
    info = {
        'url': f'http://127.0.0.1:{PORT}/api',
        'user': 'test_user',
        'password': 'test_password',
    }
    print('kadi_apps.tests.conftest Starting Flask App')
    p = Process(target=_run_app)
    p.start()
    r = None
    errors = []
    tries = 30
    for _ in range(tries):
        try:
            print(f'kadi_apps.tests.conftest Trying {info["url"]}')
            r = requests.get(info['url'])
            break  # if there is any response we call it a success
        except Exception:
            errors.append(traceback.format_exc())
            time.sleep(1)
    if r is None:
        p.kill()
        pytest.fail(f'Test server failed to start ({errors[-1]})')
    else:
        yield info
        print('kadi_apps.tests.conftest Killing Flask App')
        p.kill()
        print('kadi_apps.tests.conftest done')

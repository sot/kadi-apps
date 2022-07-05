import pytest
import time


def _run_app():
    import kadi_apps.app
    app = kadi_apps.app.get_app(settings='unit_test')
    app.run(host='0.0.0.0', debug=False)


@pytest.fixture(scope="session")
def test_server(request):
    import requests
    from multiprocessing import Process
    info = {
        'url': 'http://127.0.0.1:5000',
        'user': 'test_user',
        'password': 'test_password',
    }
    print('kadi_apps.tests.conftest Starting Flask App')
    p = Process(target=_run_app)
    p.start()
    r = None
    errors = []
    tries = 40
    for _ in range(tries):
        try:
            r = requests.get(info['url'])
            break  # if there is any response we call it a success
        except Exception as e:
            errors.append(str(e))
            time.sleep(0.2)
    if r is None:
        p.kill()
        error = 'timeout' if len(errors) == tries else errors[-1]
        pytest.fail(f'Test server failed to start ({error})')
    else:
        yield info
        print('kadi_apps.tests.conftest Killing Flask App')
        p.kill()
        print('kadi_apps.tests.conftest done')

import flask
import kadi_apps
import kadi


def _ska3_flight_version():
    import subprocess
    from pathlib import Path
    import os
    import json
    env = dict(os.environ)
    conda = None
    version = 'Unknown'
    for conda_exec in ['conda', Path(env.get('SKA', '')) / 'bin' / 'conda']:
        if not subprocess.run(['which', conda_exec], capture_output=True).returncode:
            conda = conda_exec
            break
    if conda is not None:
        try:
            r = subprocess.run([conda, 'list', 'ska3-flight', '--json'], capture_output=True)
            conda_list = json.loads(r.stdout.decode())
            if conda_list:
                version = conda_list[0]['version']
        except Exception:
            pass
    return version


CONTEXT = {
    'kadi_apps_version': kadi_apps.__version__,
    'kadi_version': kadi.__version__,
    'ska3_flight_version': _ska3_flight_version(),
}


def render_template(*args, **kwargs):
    kwargs.update(CONTEXT)
    return flask.render_template(*args, **kwargs)

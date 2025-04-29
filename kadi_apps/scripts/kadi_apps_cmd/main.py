"""
Run kadi-apps.

This script is a wrapper around the flask server for kadi-apps. Arguments are optional.
The default action is to start the server and open in the browser (show)

The script can start, stop, and show the status of the server.
The server process is managed using supervisord, and the script can be used to start/stop
supervisord, which in turn kills the server.

The script can also create and update the conda environment used to run the server.
"""

import os
import argparse
import subprocess
import webbrowser
import socket
import time
import datetime
import psutil
import textwrap

from pathlib import Path
from configparser import ConfigParser


from .task_list import task, TASK_LIST


CONFIG_FILE = str(Path(__file__).parent / "supervisord.conf")
KADI_APPS_ENV = "ska3-env-for-kadi-apps"


def get_supervisor_config():
    """Get the supervisord configuration."""
    config = ConfigParser()
    with open(CONFIG_FILE) as fh:
        config.read_file(fh)
    return config

def get_supervisor_pid():
    """Get the ID of the running supervisord process. If not running, return None."""

    config = get_supervisor_config()
    pidfile = Path(config.get("supervisord", "pidfile"))
    if pidfile.exists():
        with open(pidfile) as fh:
            pid = int(fh.read().strip())
            if psutil.pid_exists(pid):
                return pid


def _child_env_():
    """
    Utility function to create a clean environment for the child process.
    """
    # This environment is used to run commands in the child environment.
    # I don't know at this time what is the issue, but the symptom is the following.
    # Let's say I have a command such as
    #    cmd = ["env"]
    # then the following command will fail
    #    subprocess.run(["conda", "run", "-n", KADI_APPS_ENV] + cmd)
    # with the following error (note the repeated envs/ska3-env-for-kadi-apps/)
    #    EnvironmentLocationNotFound: Not a conda environment:
    #    /Users/javierg/SAO/miniconda3/envs/ska3-env-for-kadi-apps/envs/ska3-env-for-kadi-apps
    # whereas this one succeeds
    #    subprocess.run(cmd, env=_child_env_())
    env = os.environ.copy()
    # remove enything below CONDA_PREFIX from PATH
    # if I do not remove CONDA_PREFIX/bin, conda will create the environment in
    # CONDA_PREFIX/envs/{KADI_APPS_ENV}
    prefix = Path(os.environ["CONDA_PREFIX"]).parent / KADI_APPS_ENV
    paths = [str(prefix / "bin")]
    paths += [p for p in env["PATH"].split(":") if not Path(p).is_relative_to(env["CONDA_PREFIX"])]
    env["PATH"] = ":".join(paths)
    # not necessary, but I want to make sure that the new environment does not inherit anything
    env["CONDA_PREFIX"] = str(prefix)
    for key in ["CONDA_PROMPT_MODIFIER", "CONDA_DEFAULT_ENV"]:
        if key in env:
            del env[key]
    return env


@task(dependencies=["create-env"])
def start_supervisor():
    """Start supervisord process."""
    config = get_supervisor_config()
    env = {f"ENV_{key}": val for key, val in os.environ.items()}
    configdir = Path(config.get("supervisord", "logfile"), vars=env).parent
    configdir.expanduser().mkdir(parents=True, exist_ok=True)
    if not get_supervisor_pid():
        subprocess.run(["supervisord", "-c", CONFIG_FILE], env=_child_env_())


@task
def kill_supervisor():
    """Kill supervisord process (and any child process with it)."""
    if pid := get_supervisor_pid():
        subprocess.run(["kill", str(pid)])


@task(dependencies=["start-supervisor"])
def start():
    """Start kadi-apps flask server."""
    subprocess.run(
        ["supervisorctl", "-c", CONFIG_FILE, "start", "kadi-apps"],
        env=_child_env_()
    )


@task(dependencies=["start-supervisor"])
def stop():
    """Stop kadi-apps flask server."""
    subprocess.run(
        ["supervisorctl", "-c", CONFIG_FILE, "stop", "kadi-apps"],
        env=_child_env_()
    )


@task(dependencies=["create-env"])
def status():
    """Display status of supervisord and kadi-apps server."""
    pid = get_supervisor_pid()
    if pid:
        p = psutil.Process(pid)
        dt = str(datetime.timedelta(seconds=time.time() - p.create_time())).split('.')[0]
        print(
            f"supervisord                      RUNNING   pid {pid}, uptime {dt}"
        )
        subprocess.run(
            ["supervisorctl", "-c", CONFIG_FILE, "status", "kadi-apps"],
            env=_child_env_()
        )
    else:
        print("supervisord                      STOPPED")


@task(dependencies=["start"])
def show():
    """Start the kadi-apps server and open the browser."""
    for _ in range(20):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        port_is_open = (sock.connect_ex(('127.0.0.1',5000)) == 0)
        if port_is_open:
            break
        time.sleep(0.5)
    if not port_is_open:
        raise RuntimeError("Server did not start")

    url = "http://127.0.0.1:5000/"
    webbrowser.open(url, new=2)


@task
def create_env():
    """Create the conda environment for kadi-apps."""
    if not (Path(os.environ["CONDA_PREFIX"]).parent / KADI_APPS_ENV).exists():
        update_env()


@task
def update_env():
    """Update the conda environment for kadi-apps."""
    env_file = Path(__file__).parent / "environment.yml"
    subprocess.run(
        ["conda", "env", "update", "--prune", "-n", KADI_APPS_ENV, "-f", env_file],
        env=_child_env_()
    )


def get_parser():
    epilog = """
    
    Available actions:\n"""
    for action in TASK_LIST:
        epilog += f"        {action:16s} {TASK_LIST[action].__doc__}\n"
    epilog = textwrap.dedent(epilog)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog
    )
    parser.add_argument("action", choices=list(TASK_LIST), nargs='?', default="show")
    return parser


def main():
    args = get_parser().parse_args()
    if args.action in TASK_LIST:
        TASK_LIST[args.action]()


if __name__ == "__main__":
    main()
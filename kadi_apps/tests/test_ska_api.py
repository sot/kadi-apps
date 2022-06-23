import numpy as np
import requests
import re
from astropy.table import Table

from kadi.commands import get_starcats
from kadi.commands import get_observations


def test_starcheck_att(test_server):
    from mica.starcheck import get_att
    obsid = 8008
    api_url = f"{test_server['url']}/ska_api"
    path = 'mica/starcheck/get_att'
    response = requests.get(f"{api_url}/{path}?{obsid=}")
    att = get_att(obsid=obsid)
    assert att == response.json()


def test_starcheck_dither(test_server):
    from mica.starcheck import get_dither
    obsid = 8008
    api_url = f"{test_server['url']}/ska_api"
    path = 'mica/starcheck/get_dither'
    response = requests.get(f"{api_url}/{path}?{obsid=}")
    dither = get_dither(obsid=obsid)
    assert dither == response.json()


def test_starcheck_starcat(test_server):
    from mica.starcheck import get_starcat
    obsid = 8008
    api_url = f"{test_server['url']}/ska_api"
    path = 'mica/starcheck/get_starcat'
    response = requests.get(f"{api_url}/{path}?{obsid=}")
    starcat = get_starcat(obsid=obsid)
    starcat_api = Table(response.json())
    assert np.all(starcat == starcat_api)


def test_starcheck_catalog(test_server):
    from mica.starcheck import get_starcheck_catalog, get_starcheck_catalog_at_date

    obsid = 8008
    api_url = f"{test_server['url']}/ska_api"
    path = 'mica/starcheck/get_starcheck_catalog'
    response = requests.get(f"{api_url}/{path}?{obsid=}")
    catalog = get_starcheck_catalog(obsid=obsid)
    catalog_api = response.json()
    catalog_api['manvr'] = Table(catalog_api['manvr'])
    catalog_api['cat'] = Table(catalog_api['cat'])
    keys = list(catalog.keys())
    for key in keys:
        assert np.all(catalog[key] == catalog_api[key])

    date = '2007:002:04:31:43.965'
    path = 'mica/starcheck/get_starcheck_catalog_at_date'
    response = requests.get(f"{api_url}/{path}?{date=}")
    catalog = get_starcheck_catalog_at_date(date=date)
    catalog_api = response.json()
    catalog_api['manvr'] = Table(catalog_api['manvr'])
    catalog_api['cat'] = Table(catalog_api['cat'])
    keys = list(catalog.keys())
    for key in keys:
        assert np.all(catalog[key] == catalog_api[key])


def test_starcheck_monitor_windows(test_server):
    from mica.starcheck import get_monitor_windows

    api_url = f"{test_server['url']}/ska_api"

    start, stop = '2010:010', '2010:020'
    path = 'mica/starcheck/get_monitor_windows'

    windows = get_monitor_windows(start, stop)
    response = requests.get(f"{api_url}/{path}?{start=}&{stop=}")
    windows_api = response.json()
    windows_api[0]['catalog']['warnings'] = Table(windows_api[0]['catalog']['warnings'])
    windows_api[0]['catalog']['cat'] = Table(windows_api[0]['catalog']['cat'])
    windows_api[0]['catalog']['manvr'] = Table(windows_api[0]['catalog']['manvr'])
    windows_api = Table(windows_api)
    keys = list(windows.keys())
    keys.remove('catalog')

    assert np.all(windows[keys] == windows_api[keys])


def test_dark_cal_image(test_server):
    from mica.archive.aca_dark import dark_cal

    date = '2022:001'
    api_url = f"{test_server['url']}/ska_api"
    path = 'mica/archive/aca_dark/dark_cal/get_dark_cal_id'
    url = f"{api_url}/{path}?date='{date}'"
    r = requests.get(url)
    dark_cal_id = dark_cal.get_dark_cal_id(date=date)
    assert dark_cal_id == r.json()


def test_dark_cal_props(test_server):
    from mica.archive.aca_dark import dark_cal

    date = '2022:001'
    api_url = f"{test_server['url']}/ska_api"
    path = 'mica/archive/aca_dark/dark_cal/get_dark_cal_id'
    url = f"{api_url}/{path}?date='{date}'"
    r = requests.get(url)
    dark_cal_id = dark_cal.get_dark_cal_id(date=date)
    assert dark_cal_id == r.json()


def test_dark_cal_id(test_server):
    from mica.archive.aca_dark import dark_cal

    date = '2022:001'
    api_url = f"{test_server['url']}/ska_api"
    path = 'mica/archive/aca_dark/dark_cal/get_dark_cal_id'
    url = f"{api_url}/{path}?date='{date}'"
    r = requests.get(url)
    dark_cal_id = dark_cal.get_dark_cal_id(date=date)
    assert dark_cal_id == r.json()


def test_starcats(test_server):
    api_url = f"{test_server['url']}/ska_api"
    start = '2022:001'
    stop = '2022:002'
    obsid = None
    starcats = get_starcats(start=start, stop=stop, obsid=obsid, scenario='flight')
    url = f'{api_url}/kadi/commands/get_starcats?{start=}&{stop=}&scenario=flight'
    r = requests.get(url)
    starcats_api = [Table(cat) for cat in r.json()]
    colnames = [
        'slot', 'idx', 'id', 'type', 'sz', 'mag', 'maxmag', 'yang', 'zang', 'dim', 'res', 'halfw'
    ]
    for i in range(len(starcats)):
        for col in colnames:
            assert np.all(starcats[i][col] == starcats_api[i][col])
        assert np.all(starcats[i] == starcats_api[i])


def test_observations(test_server):
    api_url = f"{test_server['url']}/ska_api"
    starcat_date = '2022:001:17:00:58.521'
    observation = get_observations(starcat_date=starcat_date, scenario='flight')[0]
    url = f'{api_url}/kadi/commands/get_observations?{starcat_date=}&scenario=flight'
    r = requests.get(url)
    assert r.ok
    observation_api = r.json()[0]
    for key in observation_api:
        if isinstance(observation_api[key], list):
            observation_api[key] = tuple(observation_api[key])
    assert observation_api == observation


def test_errors(test_server):
    api_url = f"{test_server['url']}/ska_api"

    # this function is not allowed
    url = f"{api_url}/mica/archive/aca_dark/dark_cal/get_dark_cal_dirs"
    r = requests.get(url)
    assert not r.ok
    assert r.reason == 'NOT FOUND'
    assert 'error' in r.json()
    assert re.match('function get_dark_cal_dirs was not found or is not allowed', r.json()['error'])

    # this module does not exist
    url = f"{api_url}/mica/archive/aca_dark/dark_cal2/get_dark_cal_id"
    r = requests.get(url)
    assert not r.ok
    assert r.reason == 'NOT FOUND'
    assert 'error' in r.json()
    assert re.match('no app module found for URL path', r.json()['error'])

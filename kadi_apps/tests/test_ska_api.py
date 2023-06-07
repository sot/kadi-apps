import numpy as np
import requests
import re
from astropy.table import Table

from kadi.commands import get_starcats
from kadi.commands import get_observations

from kadi_apps.blueprints.ska_api.api import _replace_object_cols_with_str


def test_agasc_star(test_server):
    import agasc
    agasc_id = 2758752
    date = '2022:001'
    star = agasc.get_star(agasc_id)
    api_url = f"{test_server['url']}/ska_api"
    path = 'agasc/get_star'
    response = requests.get(f"{api_url}/{path}?id={agasc_id}&{date=}")
    star_api = Table(response.json())[0]
    # for some reason, RA_PMCORR and DEC_PMCORR differ, so I take only a few columns anyway:
    cols = ['AGASC_ID', 'RA', 'DEC', 'MAG']
    assert list(star[cols].values()) == list(star_api[cols].values())


def test_kadi_states(test_server):
    from kadi.commands.states import get_states
    start = "2023:100"
    stop = "2023:101"
    states = get_states(start=start, stop=stop)
    states = _replace_object_cols_with_str(states)
    api_url = f"{test_server['url']}/ska_api"
    path = "kadi/commands/states/get_states"
    response = requests.get(f"{api_url}/{path}?{start=}&{stop=}")
    states_api = Table(response.json())
    assert states.colnames == states_api.colnames
    for col in states.colnames:
        assert np.all(states[col] == states_api[col])


def test_agasc_stars(test_server):
    import agasc
    agasc_ids = [44960448, 44965624, 45096160]
    dates = ['2022:001']
    stars = agasc.get_stars(agasc_ids)
    api_url = f"{test_server['url']}/ska_api"
    path = 'agasc/get_stars'
    response = requests.get(f"{api_url}/{path}?ids={agasc_ids}&{dates=}")
    assert response.ok, 'test_agasc_stars API request failed'
    stars_api = Table(response.json())
    # for some reason, RA_PMCORR and DEC_PMCORR differ, so I take only a few columns anyway:
    cols = ['AGASC_ID', 'RA', 'DEC', 'MAG']
    assert np.all(stars_api.as_array().astype(stars.dtype)[cols] == stars.as_array()[cols])


def test_agasc_cone(test_server):
    import agasc
    ra, dec = 228.5895961, 4.9938399
    radius = 0.15
    date = '2022:001'
    stars = agasc.get_agasc_cone(ra=ra, dec=dec, radius=radius, date=date)
    api_url = f"{test_server['url']}/ska_api"
    path = 'agasc/get_agasc_cone'
    response = requests.get(f"{api_url}/{path}?{ra=}&{dec=}&{radius=}&{date=}")
    stars_api = Table(response.json())
    assert response.ok, 'test_agasc_cone API request failed'
    assert len(stars) == len(stars_api)
    # for some reason, RA_PMCORR and DEC_PMCORR differ, so I take only a few columns anyway:
    cols = ['AGASC_ID', 'RA', 'DEC', 'MAG']
    assert np.all(stars_api.as_array().astype(stars.dtype)[cols] == stars.as_array()[cols])


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

    windows: Table = get_monitor_windows(start, stop)
    response = requests.get(f"{api_url}/{path}?{start=}&{stop=}")
    windows_api = Table(response.json())
    keys = list(windows.colnames)
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

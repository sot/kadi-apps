import json
import re

import astropy.units as u
import numpy as np
import pytest
import requests
from astropy.table import Table
from astropy.time import Time
from cxotime import CxoTime
from kadi.commands import get_observations, get_starcats
from Quaternion import Quat

from kadi_apps.blueprints.ska_api.api import APIEncoder, _replace_object_cols_with_str


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
    cols = ['AGASC_ID', 'RA', 'DEC', 'MAG_ACA']
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
    cols = ['AGASC_ID', 'RA', 'DEC', 'MAG_ACA']
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
    cols = ['AGASC_ID', 'RA', 'DEC', 'MAG_ACA']
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


def _interpret_aca_table(data):
    from proseco.catalog import ACATable, AcqTable, GuideTable
    meta = data["meta"].copy()
    meta["acqs"] = AcqTable(meta["acqs"]["columns"], meta=meta["acqs"]["meta"])
    meta["guides"] = GuideTable(meta["guides"]["columns"], meta=meta["guides"]["meta"])
    meta["att"] = Quat(meta["att"]["q"])
    starcat = ACATable(data["columns"], meta=meta)
    return starcat


def test_starcats_full(test_server):
    api_url = f"{test_server['url']}/ska_api"
    start = '2022:001'
    stop = '2022:002'
    obsid = None
    starcats = get_starcats(start=start, stop=stop, obsid=obsid, scenario='flight')
    url = f'{api_url}/kadi/commands/get_starcats?{start=}&{stop=}&scenario=flight&table_format=full'
    r = requests.get(url)
    assert r.ok
    starcats_api = [_interpret_aca_table(cat) for cat in r.json()]
    assert len(starcats) == len(starcats_api)
    for i in range(len(starcats)):
        sc = starcats[i]
        sc_api = starcats_api[i]
        assert np.all(sc == sc_api), f"starcat {sc.date} data does not match API output"

        assert np.all(sc.meta['acqs'] == sc_api.meta['acqs']), f"starcat {sc.date} acqs does not match API output"
        assert np.all(sc.meta['guides'] == sc_api.meta['guides']), f"starcat {sc.date} guides does not match API output"
        assert sc.date == sc_api.date, f"starcat {sc.date} date does not match API output"
        assert sc.obsid == sc_api.obsid, f"starcat {sc.date} obsid does not match API output"
        assert sc.duration == sc_api.duration, f"starcat {sc.date} duration does not match API output"
        assert sc.detector == sc_api.detector, f"starcat {sc.date} detector does not match API output"
        assert sc.sim_offset == sc_api.sim_offset, f"starcat {sc.date} sim_offset does not match API output"
        assert sc.t_ccd_guide == sc_api.t_ccd_guide, f"starcat {sc.date} t_ccd_guide does not match API output"
        assert sc.t_ccd_acq == sc_api.t_ccd_acq, f"starcat {sc.date} t_ccd_acq does not match API output"


def _encode_meta_value(val, table_format='full'):
    """Put ``val`` in the meta of a table and return its encoded form"""
    tbl = Table({'a': [1]})
    tbl.meta['val'] = val
    out = json.loads(APIEncoder(table_format=table_format).encode(tbl))
    return out['meta']['val']


@pytest.mark.parametrize(
    'val,expected',
    [
        (np.bool_(True), True),
        (np.int8(-1), -1),
        (np.int16(-2), -2),
        (np.int32(-3), -3),
        (np.int64(-4), -4),
        (np.uint8(1), 1),
        (np.uint16(2), 2),
        (np.uint32(3), 3),
        (np.uint64(4), 4),
        (np.float16(1.5), 1.5),
        (np.float32(2.5), 2.5),
        (np.float64(3.5), 3.5),
        (np.str_('abc'), 'abc'),
    ]
)
def test_encode_numpy_scalars(val, expected):
    """Numpy scalars of any size or kind are encoded as the native Python value"""
    assert _encode_meta_value(val) == expected


def test_encode_quantity():
    assert _encode_meta_value(3.0 * u.deg) == {
        'class_name': 'Quantity',
        'full_name': 'astropy.units.quantity.Quantity',
        'value': 3.0,
        'unit': 'deg',
    }
    assert _encode_meta_value([1.0, 2.0] * u.deg)['value'] == [1.0, 2.0]


def test_encode_time():
    """A Time is encoded with what is needed to reconstruct it"""
    time = CxoTime('2022:001:12:00:00.000')
    out = _encode_meta_value(time)
    assert out['class_name'] == 'CxoTime'
    assert CxoTime(out['value'], format=out['format'], scale=out['scale']) == time
    assert _encode_meta_value(Time('2022-01-01'))['class_name'] == 'Time'


def test_encode_object_class_info_only_for_full():
    """Class info is included in the 'full' format only"""
    quat = Quat([0, 0, 0, 1])
    assert _encode_meta_value(quat)['q'] == [0.0, 0.0, 0.0, 1.0]
    # The other formats do not include meta at all, so encode the Quat directly.
    for table_format in ('rows', 'columns'):
        encoded = APIEncoder(table_format=table_format).encode(quat)
        assert json.loads(encoded) == [0.0, 0.0, 0.0, 1.0]


def test_encode_unserializable_meta():
    """A meta value that cannot be encoded is replaced by a stable marker"""
    tbl = Table({'a': [1]})
    tbl.meta['good'] = 1
    tbl.meta['nested'] = {'bad': object()}
    out = json.loads(APIEncoder(table_format='full').encode(tbl))
    assert out['meta']['good'] == 1
    assert out['meta']['nested']['bad'] == {'__unserializable__': 'builtins.object'}


def test_cmds_full(test_server):
    """get_cmds meta holds a weakref, which must not fail the request"""
    api_url = f"{test_server['url']}/ska_api"
    start = '2022:001'
    stop = '2022:002'
    url = f'{api_url}/kadi/commands/get_cmds?{start=}&{stop=}&scenario=flight&table_format=full'
    r = requests.get(url)
    assert r.ok
    out = r.json()
    assert out['class_name'] == 'CommandTable'
    assert len(out['columns']['idx']) > 0
    rev_pars_dict = out['meta']['__attributes__']['rev_pars_dict']
    assert rev_pars_dict == {'__unserializable__': 'weakref.ReferenceType'}


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

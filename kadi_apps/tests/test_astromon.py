import json
import requests
import numpy as np


def test_matches(test_server):
    r = requests.get(f'{test_server["url"]}/astromon/matches')
    assert r.ok
    content = json.loads(r.content.decode())
    assert list(content.keys()) == ['matches', 'time_range']
    assert isinstance(content['matches'], list)
    assert len(content['matches']) > 0
    assert isinstance(content['matches'][0], dict)
    assert list(content['matches'][0].keys()) == [
        'c_id', 'catalog', 'category', 'date_iso', 'detector', 'dr', 'dy', 'dz', 'grating', 'idx',
        'name', 'obsid', 'snr', 'target', 'time', 'x_id'
    ]


def test_obsid_auth(test_server):
    r = requests.get(f'{test_server["url"]}/astromon')
    assert not r.ok
    assert r.reason == 'UNAUTHORIZED'


def test_obsid(test_server):
    r = requests.post(
        f'{test_server["url"]}/auth/token',
        json={'user': test_server["user"], 'password': test_server["password"]}
    )
    token = json.loads(r.text)['token']

    r = requests.get(
        f'{test_server["url"]}/astromon',
        json={'obsid': 8008},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.ok
    data = json.loads(r.text)
    assert data['obsid'] == 8008
    assert list(data.keys()) == [
        'image', 'matches', 'obsid', 'obspar', 'regions', 'rough_matches',
        'simbad_url', 'sources', 'sources_new'
    ]
    d = np.array(data['image'])
    assert d.dtype == np.dtype('float64')
    assert d.shape == (720, 720)
    assert data['obspar']['detector'] == 'ACIS-I'


def test_regions(test_server):
    token = json.loads(
        requests.post(
            f'{test_server["url"]}/auth/token',
            json={'user': test_server["user"], 'password': test_server["password"]}
        ).text
    )['token']

    # GET should not be allowed for security reasons (token in test_server["url"])
    r = requests.get(
        f'{test_server["url"]}/astromon/regions',
        json={'obsid': 21156},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert not r.ok
    assert r.reason == 'METHOD NOT ALLOWED'

    # POST without giving regions gets the regions
    r = requests.post(
        f'{test_server["url"]}/astromon/regions',
        json={'obsid': 21156},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.ok, 'region get failed'
    data = json.loads(r.text)
    assert not data['regions']

    # POST with regions adds them
    regions_ref = [{'obsid': 21156, 'x': 383., 'y': 361., 'radius': 5., 'comments': 'some comment'}]
    r = requests.post(
        f'{test_server["url"]}/astromon/regions',
        json={'obsid': 21156, 'regions': regions_ref},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.ok, 'region add failed'
    data = json.loads(r.text)
    regions = data['regions']
    assert len(regions) == 1
    assert regions[0]['obsid'] == regions_ref[0]['obsid']
    assert regions[0]['radius'] == regions_ref[0]['radius']
    assert regions[0]['comments'] == regions_ref[0]['comments']
    assert np.isclose(regions[0]['x'], regions_ref[0]['x'])
    assert np.isclose(regions[0]['y'], regions_ref[0]['y'])

    r = requests.delete(
        f'{test_server["url"]}/astromon/regions',
        json={'obsid': 21156, 'regions': [r['region_id'] for r in regions]},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.ok, 'region delete failed'

    r = requests.post(
        f'{test_server["url"]}/astromon/regions',
        json={'obsid': 21156},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.ok, 'region get (2) failed'

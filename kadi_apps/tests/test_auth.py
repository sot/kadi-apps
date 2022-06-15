import json
import requests
import jwt

# def test_token_expired(test_server):
#     token = (
#         'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9'
#         '.eyJ1c2VyIjoiamdvbnphbGV6IiwiZXhwIjoxNjM2NjQ3NDA1fQ'
#         '.UyLiThCmZR9SJzzoy6r1dCAnRt7y_XU6v14nEwIieis'
#     )
#     headers = {"Authorization": f"Bearer {token}"}
#     r = requests.get(f'{test_server["url"]}/test', headers=headers)
#     assert not r.ok
#     assert r.reason == 'UNAUTHORIZED'
#     assert re.search('ExpiredSignatureError', json.loads(r.text)['message'])


def test_token_forbidden(test_server):
    for method in ['get']:
        r = requests.request(method, f'{test_server["url"]}/auth/token')
        assert not r.ok
        assert r.reason == 'METHOD NOT ALLOWED'


def test_token(test_server):

    # this is how the initial login looks like:
    # it should set a cookie and return a token
    r = requests.post(
        f'{test_server["url"]}/auth/token',
        json={'user': test_server["user"], 'password': test_server["password"]}
    )
    assert r.ok
    assert r.status_code == 200
    cookies = {c.name: c for c in r.cookies}
    assert 'refresh_token' in cookies
    assert cookies['refresh_token'].secure
    assert cookies['refresh_token'].has_nonstandard_attr('HttpOnly')
    refresh_token = cookies['refresh_token'].value

    # this is how subsequent calls look like:
    # user/password are not required if the cookie is included in the request
    # if the cookie is included in the request, it should not be set in the response
    r = requests.post(f'{test_server["url"]}/auth/token', cookies={'refresh_token': refresh_token})
    assert r.ok
    assert r.status_code == 200
    assert 'refresh_token' not in r.cookies  # i.e.: it is not being changed
    data = json.loads(r.text)
    assert 'token' in data
    token = data['token']

    # this is how tokens are used in the header:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f'{test_server["url"]}/test', headers=headers)
    assert r.ok
    assert r.status_code == 200
    data = json.loads(r.text)
    assert data['message'] == 'all ok'
    assert data['user'] == test_server["user"]


def test_token_no_auth(test_server):
    r = requests.post(f'{test_server["url"]}/auth/token')
    assert not r.ok
    assert r.status_code == 403


def test_token_wrong_cookie(test_server):
    r = requests.post(f'{test_server["url"]}/auth/token', cookies={'refresh_token': 'garbage'})
    assert not r.ok
    assert r.status_code == 403


def test_token_wrong_user(test_server):
    r = requests.post(
        f'{test_server["url"]}/auth/token',
        json={'user': 'garbage', 'password': test_server["password"]}
    )
    assert not r.ok
    assert r.status_code == 403


def test_token_wrong_password(test_server):
    r = requests.post(
        f'{test_server["url"]}/auth/token',
        json={'user': test_server["user"], 'password': 'garbage'}
    )
    assert not r.ok
    assert r.status_code == 403


def test_private(test_server):
    r = requests.post(
        f'{test_server["url"]}/auth/token',
        json={'user': test_server["user"], 'password': test_server["password"]}
    )
    assert r.ok
    data = json.loads(r.text)
    assert 'token' in data
    token = data['token']

    # wrong token
    headers = {"Authorization": f"Bearer some_garbage_here"}
    r = requests.get(f'{test_server["url"]}/test', headers=headers)
    assert not r.ok
    assert r.status_code == 401

    headers = {"Authorization": f"Bearer {token[:token.rfind('.')]}"}
    r = requests.get(f'{test_server["url"]}/test', headers=headers)
    assert not r.ok
    assert r.status_code == 401
    data = json.loads(r.text)

    claims = jwt.decode(token, options={"verify_signature": False}, algorithms="none")
    unsigned_token = jwt.encode(claims, None, algorithm=None).decode()
    headers = {"Authorization": f"Bearer {unsigned_token}"}
    assert not r.ok

import requests


def test_health():
    r = requests.get("http://localhost:8000/health")
    assert r.status_code == 200


def test_list_users():
    r = requests.get("http://localhost:8000/users")
    assert r.status_code == 200

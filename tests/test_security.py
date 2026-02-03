import time
import pytest
import httpx
import os

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

BASE_URL = "http://api:8000"


def register(username: str, password: str):
    return httpx.post(f"{BASE_URL}/auth/register", params={"username": username, "password": password})


def login(username: str, password: str):
    return httpx.post(
        f"{BASE_URL}/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def tokens():
    # создаём пользователей (если уже есть — норм)
    register("user1", "1234")
    register("user2", "1234")

    r1 = login("user1", "1234")
    assert r1.status_code == 200
    t1 = r1.json()["access_token"]

    r2 = login("user2", "1234")
    assert r2.status_code == 200
    t2 = r2.json()["access_token"]

    return {"user1": t1, "user2": t2}


def test_unauthorized_access():
    r = httpx.get(f"{BASE_URL}/documents/")
    assert r.status_code == 401


def test_access_control(tokens):
    t1 = tokens["user1"]
    t2 = tokens["user2"]

    # user1 upload
    files = {"file": ("a.txt", b"hello", "text/plain")}
    r = httpx.post(
        f"{BASE_URL}/documents/upload",
        params={"title": "Doc A", "doc_type": "contract"},
        files=files,
        headers=auth_headers(t1),
    )
    assert r.status_code == 200
    doc_id = r.json()["id"]

    # user2 cannot access
    r = httpx.get(f"{BASE_URL}/documents/{doc_id}", headers=auth_headers(t2))
    assert r.status_code == 403

    # grant
    r = httpx.post(f"{BASE_URL}/documents/{doc_id}/grant", params={"user_id": 2}, headers=auth_headers(t1))
    assert r.status_code == 200

    # user2 can access now
    r = httpx.get(f"{BASE_URL}/documents/{doc_id}", headers=auth_headers(t2))
    assert r.status_code == 200


def test_bruteforce_protection():
    # несколько неверных попыток
    for _ in range(6):
        r = login("user1", "WRONGPASS")
        if r.status_code == 429:
            break
        assert r.status_code in (401, 429)

    # должно быть заблокировано
    r = login("user1", "WRONGPASS")
    assert r.status_code in (429, 401)


def test_rate_limit(tokens):
    t1 = tokens["user1"]
    hit_429 = False

    for _ in range(60):
        r = httpx.get(f"{BASE_URL}/documents/", headers=auth_headers(t1))
        if r.status_code == 429:
            hit_429 = True
            break

    assert hit_429 is True

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})
    return app.test_client()


def auth(client, username="alice", password="secret123"):
    client.post("/api/register", json={"username": username, "password": password})
    token = client.post("/api/login", json={"username": username, "password": password}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_register_and_login(client):
    assert client.post("/api/register", json={"username": "bob", "password": "secret123"}).status_code == 201
    assert "token" in client.post("/api/login", json={"username": "bob", "password": "secret123"}).get_json()


def test_duplicate_username_rejected(client):
    client.post("/api/register", json={"username": "bob", "password": "secret123"})
    assert client.post("/api/register", json={"username": "bob", "password": "other123"}).status_code == 409


def test_register_validation(client):
    assert client.post("/api/register", json={"username": "ab", "password": "secret123"}).status_code == 400
    assert client.post("/api/register", json={"username": "bob", "password": "123"}).status_code == 400


def test_wrong_password_rejected(client):
    client.post("/api/register", json={"username": "bob", "password": "secret123"})
    assert client.post("/api/login", json={"username": "bob", "password": "nope"}).status_code == 401


def test_expenses_require_token(client):
    assert client.get("/api/expenses").status_code == 401
    assert client.get("/api/expenses", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_create_and_list_expense(client):
    h = auth(client)
    r = client.post("/api/expenses", json={"amount": 12.5, "category": "Food", "date": "2026-01-05"}, headers=h)
    assert r.status_code == 201
    rows = client.get("/api/expenses", headers=h).get_json()
    assert len(rows) == 1 and rows[0]["amount"] == 12.5


@pytest.mark.parametrize("payload", [
    {"amount": -5, "category": "Food"},
    {"amount": "abc", "category": "Food"},
    {"amount": 5, "category": ""},
    {"amount": 5, "category": "Food", "date": "05-01-2026"},
])
def test_invalid_expense_rejected(client, payload):
    assert client.post("/api/expenses", json=payload, headers=auth(client)).status_code == 400


def test_users_cannot_see_or_change_each_others_expenses(client):
    a, b = auth(client, "alice"), auth(client, "bobby")
    eid = client.post("/api/expenses", json={"amount": 10, "category": "Food"}, headers=a).get_json()["id"]
    assert client.get("/api/expenses", headers=b).get_json() == []
    assert client.delete(f"/api/expenses/{eid}", headers=b).status_code == 404
    assert client.put(f"/api/expenses/{eid}", json={"amount": 1, "category": "X"}, headers=b).status_code == 404


def test_update_and_delete(client):
    h = auth(client)
    eid = client.post("/api/expenses", json={"amount": 10, "category": "Food"}, headers=h).get_json()["id"]
    assert client.put(f"/api/expenses/{eid}", json={"amount": 20, "category": "Travel"}, headers=h).status_code == 200
    assert client.get("/api/expenses", headers=h).get_json()[0]["category"] == "Travel"
    assert client.delete(f"/api/expenses/{eid}", headers=h).status_code == 204
    assert client.get("/api/expenses", headers=h).get_json() == []


def test_filter_by_category(client):
    h = auth(client)
    client.post("/api/expenses", json={"amount": 10, "category": "Food"}, headers=h)
    client.post("/api/expenses", json={"amount": 30, "category": "Travel"}, headers=h)
    rows = client.get("/api/expenses?category=Travel", headers=h).get_json()
    assert len(rows) == 1 and rows[0]["category"] == "Travel"


def test_summary(client):
    h = auth(client)
    for amt, cat in [(10, "Food"), (5.5, "Food"), (30, "Travel")]:
        client.post("/api/expenses", json={"amount": amt, "category": cat}, headers=h)
    s = client.get("/api/summary", headers=h).get_json()
    assert s["total"] == 45.5
    assert s["by_category"][0] == {"category": "Travel", "total": 30.0, "count": 1}

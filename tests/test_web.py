"""Тесты View-сервера: HTTP-маршруты корректно проксируют ViewModel."""

import pytest

from lj_md.view.app import SESSION_COOKIE, create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Леннард-Джонс" in resp.get_data(as_text=True)


def test_schema(client):
    data = client.get("/api/schema").get_json()
    names = {f["name"] for f in data["fields"]}
    assert {"n_particles", "density", "dt", "thermostat"} <= names
    assert {p["name"] for p in data["presets"]} == {"gas", "liquid", "solid"}


def test_session_cookie_and_flow(client):
    resp = client.get("/api/state")
    assert SESSION_COOKIE in resp.headers.get("Set-Cookie", "")
    assert client.post("/api/command/start").get_json()["is_running"] is True
    state = client.post("/api/tick").get_json()
    assert int(state["display"]["step"]) > 0
    assert client.post("/api/command/pause").get_json()["is_running"] is False


def test_params_errors(client):
    state = client.post("/api/params", json={"dt": "abc"}).get_json()
    assert "dt" in state["errors"]


def test_unknown_command_and_preset(client):
    assert client.post("/api/command/boom").status_code == 404
    assert client.post("/api/preset/boom").status_code == 404


def test_sessions_are_isolated():
    app = create_app()
    a, b = app.test_client(), app.test_client()
    a.post("/api/command/start")
    assert b.get("/api/state").get_json()["is_running"] is False


def test_export_csv(client):
    client.post("/api/command/step")
    resp = client.get("/api/export.csv")
    assert resp.mimetype == "text/csv"
    assert resp.get_data(as_text=True).startswith("step,time")


def test_export_json(client):
    client.post("/api/command/step")
    resp = client.get("/api/export.json")
    assert resp.mimetype == "application/json"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert resp.get_json()["format"] == "lj_md-report/1"


def test_bad_json_body_is_handled(client):
    resp = client.post("/api/params", data="не json", content_type="application/json")
    assert resp.status_code == 200
    assert resp.get_json()["errors"] == {}

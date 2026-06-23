from __future__ import annotations

from uuid import UUID

from flask import jsonify, request

from leverance.app import create_app

REQUIRED_API_ROUTES = {
    "/api/jn/fetch_status",
    "/api/jn/get_notat",
    "/api/jn/process_call",
    "/api/jn/feedback",
    "/api/jn/get_config",
    "/api/jn/insert_config",
    "/api/jn/delete_config",
    "/api/jn/sta_credentials",
    "/api/jn/get_prompt",
}


def test_create_app_registers_routes_and_healthcheck(monkeypatch):
    monkeypatch.setenv("JN_LOCAL_MODE", "1")

    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    client = app.test_client()

    assert REQUIRED_API_ROUTES.issubset(routes)

    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_app_attaches_request_uid(monkeypatch):
    monkeypatch.setenv("JN_LOCAL_MODE", "1")

    app = create_app()

    @app.get("/_uid_check")
    def uid_check():
        return jsonify(uid=str(request.uid))

    response = app.test_client().get("/_uid_check")

    assert response.status_code == 200
    uid = response.get_json()["uid"]
    assert str(UUID(uid)) == uid

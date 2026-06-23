from __future__ import annotations

import importlib
import inspect
import re
import sys
import types
from urllib.parse import parse_qs, urlparse

from leverance.components.functions.llm_helper import parse_llm_json_response


class _Param:
    def __init__(self, default=None, alias=None):
        self.default = default
        self.alias = alias


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FastAPIRoute:
    def __init__(self, path, func):
        self.path = path
        self.func = func
        self.pattern = re.compile("^" + re.sub(r"\{([^}]+)\}", r"(?P<\1>[^/]+)", path) + "$")


class _FakeFastAPI:
    def __init__(self, *args, **kwargs):
        self.routes = []

    def post(self, path):
        def decorator(func):
            self.routes.append(_FastAPIRoute(path, func))
            return func

        return decorator


class _FakeTestClient:
    def __init__(self, app):
        self.app = app

    def post(self, url, headers=None, json=None):
        headers = headers or {}
        parsed_url = urlparse(url)
        query = {key: values[-1] for key, values in parse_qs(parsed_url.query).items()}

        for route in self.app.routes:
            match = route.pattern.match(parsed_url.path)
            if not match:
                continue

            kwargs = {}
            signature = inspect.signature(route.func)
            for name, parameter in signature.parameters.items():
                if name in match.groupdict():
                    kwargs[name] = match.group(name)
                    continue

                default = parameter.default
                if name == "request":
                    kwargs[name] = parameter.annotation(**(json or {}))
                elif isinstance(default, _Param):
                    lookup_name = default.alias or name
                    kwargs[name] = query.get(lookup_name, headers.get(lookup_name, default.default))
                elif default is inspect._empty:
                    kwargs[name] = None
                else:
                    kwargs[name] = default

            return _Response(route.func(**kwargs))

        raise AssertionError(f"No matching route for {parsed_url.path}")


def _load_mock_llm_module(monkeypatch):
    try:
        import fastapi.testclient as real_testclient

        from mock_llm import app as mock_llm_app

        return mock_llm_app, real_testclient.TestClient
    except ModuleNotFoundError:
        fastapi_module = types.ModuleType("fastapi")
        fastapi_module.FastAPI = _FakeFastAPI
        fastapi_module.Header = lambda default=None, alias=None: _Param(
            default=default, alias=alias
        )
        fastapi_module.Query = lambda default=None, alias=None: _Param(default=default, alias=alias)

        testclient_module = types.ModuleType("fastapi.testclient")
        testclient_module.TestClient = _FakeTestClient

        monkeypatch.setitem(sys.modules, "fastapi", fastapi_module)
        monkeypatch.setitem(sys.modules, "fastapi.testclient", testclient_module)
        monkeypatch.delitem(sys.modules, "mock_llm.app", raising=False)

        return importlib.import_module("mock_llm.app"), _FakeTestClient


def test_mock_llm_chat_completions_returns_openai_shape(monkeypatch):
    mock_llm_app, test_client_cls = _load_mock_llm_module(monkeypatch)
    client = test_client_cls(mock_llm_app.app)

    response = client.post(
        "/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21",
        headers={"api-key": "test-key"},
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "Du er hjælpsom."},
                {"role": "user", "content": "Lav et svar i json."},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["choices"][0]["message"]["content"]
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert payload["usage"]["prompt_tokens"] > 0
    assert payload["usage"]["completion_tokens"] > 0

    parsed = parse_llm_json_response(payload["choices"][0]["message"]["content"])
    assert set(parsed) == {"oplysninger", "status"}
    assert parsed["oplysninger"]
    assert parsed["status"]

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from leverance.components.business.jn import jn_storage_account_business_component as storage_module
from leverance.components.business.jn.jn_storage_account_business_component import (
    JNStorageAccountBusinessComponent,
)
from leverance.core.runners.service_runner import ServiceRunner
from spark_core.app import App
from spark_core.config.base_config import Config


def _fake_service_runner_init(self, service_name, request_uid=None, **_kwargs):
    self.service_name = service_name
    self.request_uid = request_uid
    self.app = App(config=Config("local"), applikation=f"SERVICE_{service_name}")
    self.session = None
    self.sessions = {}
    self.threadpool = None


def test_get_token_returns_local_token(monkeypatch):
    monkeypatch.setenv("JN_LOCAL_MODE", "1")
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(ServiceRunner, "__init__", _fake_service_runner_init)

    component = JNStorageAccountBusinessComponent(uuid4())
    token = component.get_token()

    assert component.TTL == 3600
    assert token["token"] == "local-development-token"
    assert isinstance(token["expires_on"], datetime)


def test_create_container_client_uses_connection_string_branch(monkeypatch):
    monkeypatch.setenv("JN_LOCAL_MODE", "1")
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setattr(ServiceRunner, "__init__", _fake_service_runner_init)

    called = {}
    sentinel = object()

    class FakeContainerClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("prod ContainerClient path should not be used in local mode")

        @classmethod
        def from_connection_string(cls, conn_str, container_name):
            called["conn_str"] = conn_str
            called["container_name"] = container_name
            return sentinel

    monkeypatch.setattr(storage_module, "ContainerClient", FakeContainerClient)

    component = JNStorageAccountBusinessComponent(uuid4())

    assert component.create_container_client("transcriptions") is sentinel
    assert called == {
        "conn_str": "UseDevelopmentStorage=true",
        "container_name": "transcriptions",
    }


def test_create_queue_client_uses_connection_string_branch(monkeypatch):
    monkeypatch.setenv("JN_LOCAL_MODE", "1")
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true")
    monkeypatch.setattr(ServiceRunner, "__init__", _fake_service_runner_init)

    called = {}

    class FakeQueueClient:
        def __init__(self):
            self.created = False

        def get_queue_properties(self):
            raise RuntimeError("queue missing")

        def create_queue(self):
            self.created = True

    class FakeQueueServiceClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("prod QueueServiceClient path should not be used in local mode")

        @classmethod
        def from_connection_string(cls, conn_str):
            called["conn_str"] = conn_str
            client = object.__new__(cls)
            called["queue_client"] = FakeQueueClient()
            return client

        def get_queue_client(self, queue_name):
            called["queue_name"] = queue_name
            return called["queue_client"]

    monkeypatch.setattr(storage_module, "QueueServiceClient", FakeQueueServiceClient)

    component = JNStorageAccountBusinessComponent(uuid4())
    queue_client = component.create_queue_client("Status-TEST")

    assert called["conn_str"] == "UseDevelopmentStorage=true"
    assert called["queue_name"] == "status-test"
    assert queue_client is called["queue_client"]
    assert queue_client.created is True

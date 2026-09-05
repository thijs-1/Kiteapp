"""Tests for the request activity logging middleware."""
import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.activity_log import (
    LOGGER_NAME,
    ActivityLogMiddleware,
    anonymize_ip,
    setup_activity_logging,
)


def _read_records(log_file):
    if not log_file.exists():
        return []
    return [json.loads(line) for line in log_file.read_text().splitlines() if line]


def _make_app(anonymize_ips=False):
    app = FastAPI()

    @app.get("/spots")
    async def spots():
        return [{"id": "spot1"}]

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    app.add_middleware(
        ActivityLogMiddleware,
        exclude_paths=["/health"],
        anonymize_ips=anonymize_ips,
    )
    return app


@pytest.fixture
def log_file(tmp_path):
    path = tmp_path / "activity.jsonl"
    setup_activity_logging(log_file=path, retention_days=3, stdout=False)
    yield path
    # Detach handlers so the tmp dir can be cleaned up
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


@pytest.fixture
def client(log_file):
    return TestClient(_make_app(), raise_server_exceptions=False)


class TestActivityLogMiddleware:
    def test_one_record_per_request_with_expected_fields(self, client, log_file):
        client.get(
            "/spots?wind_min=10&country=NL",
            headers={"user-agent": "pytest-agent", "referer": "https://wheretokite.com/"},
        )

        records = _read_records(log_file)
        assert len(records) == 1
        record = records[0]
        assert record["method"] == "GET"
        assert record["path"] == "/spots"
        assert record["query"] == "wind_min=10&country=NL"
        assert record["status"] == 200
        assert record["user_agent"] == "pytest-agent"
        assert record["referer"] == "https://wheretokite.com/"
        assert record["ip"] == "testclient"  # TestClient's fake peer address
        assert record["duration_ms"] >= 0
        assert record["ts"].endswith("+00:00")

    def test_empty_query_is_null(self, client, log_file):
        client.get("/spots")
        assert _read_records(log_file)[0]["query"] is None

    def test_forwarded_for_wins_over_socket_address(self, client, log_file):
        client.get(
            "/spots",
            headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1", "x-real-ip": "198.51.100.2"},
        )
        assert _read_records(log_file)[0]["ip"] == "203.0.113.7"

    def test_real_ip_used_when_no_forwarded_for(self, client, log_file):
        client.get("/spots", headers={"x-real-ip": "198.51.100.2"})
        assert _read_records(log_file)[0]["ip"] == "198.51.100.2"

    def test_excluded_paths_and_preflights_are_not_logged(self, client, log_file):
        client.get("/health")
        client.options("/spots")
        assert _read_records(log_file) == []

    def test_not_found_logs_actual_status(self, client, log_file):
        client.get("/does-not-exist")
        assert _read_records(log_file)[0]["status"] == 404

    def test_unhandled_exception_logs_500(self, client, log_file):
        response = client.get("/boom")
        assert response.status_code == 500
        records = _read_records(log_file)
        assert len(records) == 1
        assert records[0]["status"] == 500

    def test_anonymize_option_coarsens_ip(self, log_file):
        client = TestClient(_make_app(anonymize_ips=True))
        client.get("/spots", headers={"x-forwarded-for": "203.0.113.77"})
        assert _read_records(log_file)[0]["ip"] == "203.0.113.0"

    def test_setup_is_idempotent(self, log_file, tmp_path):
        # Calling setup again must replace, not stack, handlers.
        setup_activity_logging(log_file=log_file, retention_days=3, stdout=False)
        setup_activity_logging(log_file=log_file, retention_days=3, stdout=False)
        TestClient(_make_app()).get("/spots")
        assert len(_read_records(log_file)) == 1


class TestAnonymizeIp:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("203.0.113.77", "203.0.113.0"),
            ("2001:db8:abcd:1234:5678::1", "2001:db8:abcd::"),
            ("not-an-ip", "not-an-ip"),
            (None, None),
        ],
    )
    def test_cases(self, raw, expected):
        assert anonymize_ip(raw) == expected

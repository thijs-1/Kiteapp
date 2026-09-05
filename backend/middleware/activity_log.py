"""Request activity logging.

A small pure-ASGI middleware that writes one JSON line per HTTP request
(client IP, method, path, query, status, duration, user agent, referer)
to a daily-rotated file and optionally to stdout.

Kept deliberately simple: no database, no external service. Traffic is
low enough that a JSONL file you can grep or load with pandas is plenty.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import sys
import time
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Iterable, Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOGGER_NAME = "kiteapp.activity"


def setup_activity_logging(
    log_file: Path,
    retention_days: int = 30,
    stdout: bool = True,
) -> logging.Logger:
    """Configure the activity logger.

    Idempotent: calling it again replaces any handlers installed earlier,
    which keeps tests independent and avoids duplicate lines on reload.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # never double-log via the root logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    plain = logging.Formatter("%(message)s")

    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        backupCount=retention_days,
        utc=True,
        encoding="utf-8",
    )
    file_handler.setFormatter(plain)
    logger.addHandler(file_handler)

    if stdout:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(plain)
        logger.addHandler(stream_handler)

    return logger


def resolve_client_ip(headers: dict[bytes, bytes], scope: Scope) -> Optional[str]:
    """Pick the client IP, preferring proxy headers set by nginx.

    Order: first hop of X-Forwarded-For, then X-Real-IP, then the socket
    peer address. Behind nginx on the same host the socket address is
    127.0.0.1, so the headers are what carry the real visitor.
    """
    forwarded = headers.get(b"x-forwarded-for")
    if forwarded:
        first = forwarded.decode("latin-1").split(",")[0].strip()
        if first:
            return first
    real_ip = headers.get(b"x-real-ip")
    if real_ip:
        value = real_ip.decode("latin-1").strip()
        if value:
            return value
    client = scope.get("client")
    if client:
        return client[0]
    return None


def anonymize_ip(ip: Optional[str]) -> Optional[str]:
    """Coarsen an IP so it no longer identifies a single host.

    IPv4 keeps the /24 (last octet zeroed), IPv6 keeps the /48.
    Unparseable values are returned unchanged.
    """
    if not ip:
        return ip
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    prefix = 24 if addr.version == 4 else 48
    network = ipaddress.ip_network(f"{addr}/{prefix}", strict=False)
    return str(network.network_address)


class ActivityLogMiddleware:
    """Log one JSON line per request to the ``kiteapp.activity`` logger."""

    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Iterable[str] = (),
        anonymize_ips: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.app = app
        self.exclude_paths = frozenset(exclude_paths)
        self.anonymize_ips = anonymize_ips
        self.logger = logger or logging.getLogger(LOGGER_NAME)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")
        if method == "OPTIONS" or path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code: Optional[int] = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            # Handler blew up before a response started; the outer
            # ServerErrorMiddleware will turn this into a 500.
            self._log(scope, method, path, 500, started)
            raise
        else:
            self._log(scope, method, path, status_code, started)

    def _log(
        self,
        scope: Scope,
        method: str,
        path: str,
        status_code: Optional[int],
        started: float,
    ) -> None:
        headers = dict(scope.get("headers") or [])
        ip = resolve_client_ip(headers, scope)
        if self.anonymize_ips:
            ip = anonymize_ip(ip)

        query = (scope.get("query_string") or b"").decode("latin-1")
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "ip": ip,
            "method": method,
            "path": path,
            "query": query or None,
            "status": status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "user_agent": _header(headers, b"user-agent"),
            "referer": _header(headers, b"referer"),
        }
        self.logger.info(json.dumps(record, ensure_ascii=False, separators=(",", ":")))


def _header(headers: dict[bytes, bytes], name: bytes) -> Optional[str]:
    value = headers.get(name)
    return value.decode("latin-1") if value else None

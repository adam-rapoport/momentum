"""POST /system/open-url: scheme allowlist + launcher invocation (P0 of the
2026-07-04 link fix: the endpoint must open browsers, never run arbitrary
things)."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
API = "/api/v1/system/open-url"


def test_opens_https_via_launcher():
    with patch("app.api.system.subprocess.Popen") as popen, patch(
        "app.api.system.sys.platform", "darwin"
    ):
        r = client.post(API, json={"url": "https://dadvibecoding.vercel.app"})
    assert r.status_code == 200
    assert popen.call_args[0][0] == ["/usr/bin/open", "https://dadvibecoding.vercel.app"]


def test_opens_mailto():
    with patch("app.api.system.subprocess.Popen") as popen, patch(
        "app.api.system.sys.platform", "darwin"
    ):
        r = client.post(API, json={"url": "mailto:someone@example.com"})
    assert r.status_code == 200
    assert popen.call_args[0][0][1].startswith("mailto:")


def test_rejects_non_allowlisted_schemes():
    for url in ("file:///etc/passwd", "javascript:alert(1)", "ftp://x", "osascript://x", ""):
        with patch("app.api.system.subprocess.Popen") as popen:
            r = client.post(API, json={"url": url})
        assert r.status_code == 400, url
        popen.assert_not_called()

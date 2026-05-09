"""Unit tests for the Gmail adapter helpers.

The Gmail API calls themselves are mocked — we're testing the pure-Python
body parser (multipart extraction, HTML stripping, header parsing) and
MIME builder. These are the bits most likely to break on real inbox
content, so they warrant coverage.
"""
from __future__ import annotations

import base64
import email
from email import policy

from app.core.integrations.gmail import (
    _build_mime_message,
    _extract_plain_text_body,
    _headers_to_dict,
    _strip_html,
)


def _b64url(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii")


# ---------- _headers_to_dict ----------


def test_headers_to_dict_lowercases_keys():
    result = _headers_to_dict(
        [
            {"name": "From", "value": "alice@example.com"},
            {"name": "SUBJECT", "value": "Hi"},
            {"name": "Message-Id", "value": "<abc@mail>"},
        ]
    )
    assert result == {
        "from": "alice@example.com",
        "subject": "Hi",
        "message-id": "<abc@mail>",
    }


def test_headers_to_dict_handles_empty():
    assert _headers_to_dict(None) == {}
    assert _headers_to_dict([]) == {}


# ---------- _strip_html ----------


def test_strip_html_basic_tags():
    html = "<p>Hello <b>world</b></p>"
    assert _strip_html(html) == "Hello world"


def test_strip_html_zaps_scripts_and_styles():
    html = (
        "<html><head><style>.x{color:red}</style><script>alert(1)</script></head>"
        "<body><p>Real content</p></body></html>"
    )
    result = _strip_html(html)
    assert "alert" not in result
    assert "color:red" not in result
    assert "Real content" in result


def test_strip_html_entities_and_br():
    html = "Hello&nbsp;there.<br>Next line.&amp;done"
    result = _strip_html(html)
    # &nbsp; becomes a non-breaking space, then _WS_RE collapses runs of
    # space/tab to a single space — so "Hello there." with single space.
    assert "Hello there." in result
    assert "Next line." in result
    assert "&done" in result


# ---------- _extract_plain_text_body ----------


def test_extract_body_from_flat_plain_part():
    payload = {
        "mimeType": "text/plain",
        "body": {"data": _b64url("Plain body here.")},
    }
    assert _extract_plain_text_body(payload) == "Plain body here."


def test_extract_body_prefers_plain_over_html_in_multipart():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": _b64url("<p>HTML version</p>")},
            },
            {
                "mimeType": "text/plain",
                "body": {"data": _b64url("Plain version")},
            },
        ],
    }
    assert _extract_plain_text_body(payload) == "Plain version"


def test_extract_body_falls_back_to_html_when_no_plain():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "text/html",
                "body": {"data": _b64url("<p>Only HTML here</p>")},
            },
        ],
    }
    assert _extract_plain_text_body(payload) == "Only HTML here"


def test_extract_body_walks_nested_multiparts():
    """Real Gmail messages often nest multipart/alternative inside
    multipart/mixed (when there are attachments)."""
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": _b64url("Nested plain text.")},
                    },
                ],
            },
            {
                "mimeType": "application/pdf",
                "body": {"attachmentId": "xyz"},
            },
        ],
    }
    assert _extract_plain_text_body(payload) == "Nested plain text."


def test_extract_body_handles_empty_parts():
    payload = {"mimeType": "multipart/alternative", "parts": []}
    assert _extract_plain_text_body(payload) == ""
    assert _extract_plain_text_body(None) == ""
    assert _extract_plain_text_body({}) == ""


# ---------- _build_mime_message ----------


def _decode_mime(raw_b64: str):
    raw_bytes = base64.urlsafe_b64decode(raw_b64.encode("ascii"))
    return email.message_from_bytes(raw_bytes, policy=policy.default)


def test_build_mime_sets_basic_headers():
    raw = _build_mime_message(
        to=["alice@example.com", "bob@example.com"],
        cc=None,
        subject="Hello",
        body_text="Greetings.",
    )
    msg = _decode_mime(raw)
    assert msg["To"] == "alice@example.com, bob@example.com"
    assert msg["Subject"] == "Hello"
    assert "Cc" not in msg
    assert "Greetings." in msg.get_content()


def test_build_mime_with_cc_and_reply_headers():
    raw = _build_mime_message(
        to=["alice@example.com"],
        cc=["carol@example.com"],
        subject="Re: launch plan",
        body_text="Thoughts attached.",
        in_reply_to="<original@mail>",
        references="<original@mail>",
    )
    msg = _decode_mime(raw)
    assert msg["Cc"] == "carol@example.com"
    assert msg["In-Reply-To"] == "<original@mail>"
    assert msg["References"] == "<original@mail>"

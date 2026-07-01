"""Tests for EmailNotifier gateway — covers configuration_status, resolve_recipients,
send_message no-recipients/disabled paths, send_async, and _normalize_attachments."""
import threading
from unittest.mock import MagicMock, patch

import pytest

from app.gateways.email_notifier import EmailNotifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_notifier(**env_overrides):
    """Return an EmailNotifier with environment vars injected via patching."""
    defaults = {
        "SMTP_HOST": "",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "",
        "SMTP_PASSWORD": "",
        "SMTP_USE_TLS": "true",
        "SMTP_USE_SSL": "false",
        "SMTP_TIMEOUT": "20",
        "SMTP_FROM_EMAIL": "",
        "SMTP_FROM_NAME": "Smart Home Alert",
        "ALERT_RECIPIENTS": "",
        "BREVO_API_KEY": "",
        "BREVO_API_URL": "https://api.brevo.com/v3/smtp/email",
    }
    defaults.update(env_overrides)
    with patch.dict("os.environ", defaults, clear=False):
        return EmailNotifier()


def _make_smtp_notifier():
    return _make_notifier(
        SMTP_HOST="smtp.example.com",
        SMTP_USERNAME="user@example.com",
        SMTP_PASSWORD="secret",
        SMTP_FROM_EMAIL="user@example.com",
    )


def _make_brevo_notifier():
    return _make_notifier(
        BREVO_API_KEY="xkeysib-test",
        SMTP_FROM_EMAIL="from@example.com",
    )


# ---------------------------------------------------------------------------
# configuration_status
# ---------------------------------------------------------------------------

class TestConfigurationStatus:
    def test_fully_disabled(self):
        n = _make_notifier()
        status = n.configuration_status()
        assert status["enabled"] is False
        assert status["provider"] == "none"
        assert "SMTP_HOST" in status["missing"]

    def test_smtp_enabled(self):
        n = _make_smtp_notifier()
        status = n.configuration_status()
        assert status["enabled"] is True
        assert status["provider"] == "smtp"
        assert status["smtp_enabled"] is True
        assert status["brevo_enabled"] is False
        assert status["missing"] == []

    def test_brevo_enabled(self):
        n = _make_brevo_notifier()
        status = n.configuration_status()
        assert status["enabled"] is True
        assert status["provider"] == "brevo"
        assert status["brevo_enabled"] is True
        assert status["smtp_enabled"] is False
        assert status["missing"] == []

    def test_smtp_preferred_over_brevo(self):
        n = _make_notifier(
            SMTP_HOST="smtp.example.com",
            SMTP_USERNAME="u",
            SMTP_PASSWORD="p",
            SMTP_FROM_EMAIL="u@example.com",
            BREVO_API_KEY="key",
        )
        assert n.provider == "smtp"

    def test_missing_fields_listed(self):
        n = _make_notifier(SMTP_HOST="smtp.example.com")
        status = n.configuration_status()
        # At minimum username is missing; password might come from SMTP_APP_PASSWORD in CI
        assert len(status["smtp_missing"]) >= 1
        assert "SMTP_USERNAME" in status["smtp_missing"]


# ---------------------------------------------------------------------------
# resolve_recipients / _parse_recipients
# ---------------------------------------------------------------------------

class TestResolveRecipients:
    def test_user_email_only(self):
        n = _make_notifier()
        result = n.resolve_recipients(user_email="a@b.com")
        assert result == ["a@b.com"]

    def test_deduplication(self):
        n = _make_notifier(ALERT_RECIPIENTS="a@b.com")
        result = n.resolve_recipients(user_email="a@b.com", include_default_recipients=True)
        assert result.count("a@b.com") == 1

    def test_include_default_recipients(self):
        n = _make_notifier(ALERT_RECIPIENTS="admin@example.com")
        result = n.resolve_recipients(user_email="u@u.com", include_default_recipients=True)
        assert "admin@example.com" in result
        assert "u@u.com" in result

    def test_extra_recipients_added(self):
        n = _make_notifier()
        result = n.resolve_recipients(extra="extra@e.com")
        assert "extra@e.com" in result

    def test_invalid_email_excluded(self):
        n = _make_notifier()
        result = n.resolve_recipients(extra="not-an-email")
        assert result == []

    def test_semicolon_separated_recipients(self):
        n = _make_notifier(ALERT_RECIPIENTS="a@a.com;b@b.com")
        assert "a@a.com" in n.default_recipients
        assert "b@b.com" in n.default_recipients

    def test_empty_recipients(self):
        n = _make_notifier()
        result = n.resolve_recipients()
        assert result == []


# ---------------------------------------------------------------------------
# send_message — paths that don't actually send email
# ---------------------------------------------------------------------------

class TestSendMessageNoSend:
    def test_returns_no_recipients_when_empty(self):
        n = _make_notifier()
        result = n.send_message(subject="S", body="B", recipients=[])
        assert result["sent"] is False
        assert result["reason"] == "no-recipients"

    def test_returns_disabled_when_not_configured(self):
        n = _make_notifier()
        result = n.send_message(subject="S", body="B", recipients=["a@b.com"])
        assert result["sent"] is False
        assert result["reason"] == "email-not-configured"

    def test_none_recipients_treated_as_empty(self):
        n = _make_notifier()
        result = n.send_message(subject="S", body="B", recipients=None)
        assert result["sent"] is False

    def test_no_recipients_still_resolves_gracefully(self):
        n = _make_notifier()
        result = n.send_message("sub", "body", recipients=["not-valid"])
        assert result["sent"] is False
        assert result["reason"] == "no-recipients"


# ---------------------------------------------------------------------------
# send_message — SMTP path (mocked)
# ---------------------------------------------------------------------------

class TestSendMessageSMTP:
    def test_smtp_send_called(self):
        n = _make_smtp_notifier()
        with patch.object(n, "_send_via_smtp", return_value={"sent": True, "recipients": ["r@r.com"]}) as mock_send:
            result = n.send_message("Sub", "Body", recipients=["r@r.com"])
        mock_send.assert_called_once()
        assert result["sent"] is True

    def test_smtp_receives_correct_args(self):
        n = _make_smtp_notifier()
        with patch.object(n, "_send_via_smtp", return_value={"sent": True}) as mock_send:
            n.send_message("Sub", "Body", recipients=["r@r.com"], html_body="<b>Body</b>")
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["subject"] == "Sub"
        assert call_kwargs["html_body"] == "<b>Body</b>"


# ---------------------------------------------------------------------------
# send_message — Brevo path (mocked)
# ---------------------------------------------------------------------------

class TestSendMessageBrevo:
    def test_brevo_send_called(self):
        n = _make_brevo_notifier()
        with patch.object(n, "_send_via_brevo", return_value={"sent": True}) as mock_send:
            result = n.send_message("Sub", "Body", recipients=["r@r.com"])
        mock_send.assert_called_once()
        assert result["sent"] is True


# ---------------------------------------------------------------------------
# send_async
# ---------------------------------------------------------------------------

class TestSendAsync:
    def test_send_async_fires_thread(self):
        n = _make_notifier()
        send_called = threading.Event()

        def mock_send(**kwargs):
            send_called.set()
            return {"sent": False, "reason": "email-not-configured"}

        with patch.object(n, "send_message", side_effect=mock_send):
            n.send_async("Sub", "Body", recipients=["a@b.com"])
            assert send_called.wait(timeout=3), "send_message was not called within 3 seconds"

    def test_send_async_does_not_block(self):
        """send_async returns immediately even when send_message is slow."""
        n = _make_notifier()

        slow_done = threading.Event()

        def slow_send(**kwargs):
            import time
            time.sleep(0.5)
            slow_done.set()
            return {"sent": False, "reason": "disabled"}

        with patch.object(n, "send_message", side_effect=slow_send):
            n.send_async("Sub", "Body", recipients=["a@b.com"])
            # should return before slow_send finishes
            assert not slow_done.is_set(), "send_async should have returned immediately"
        slow_done.wait(timeout=2)

    def test_send_async_no_recipients(self):
        """send_async with no recipients should not raise."""
        n = _make_notifier()
        with patch.object(n, "send_message", return_value={"sent": False, "reason": "no-recipients"}) as m:
            n.send_async("Sub", "Body", recipients=[])
            import time; time.sleep(0.2)
        m.assert_called_once()


# ---------------------------------------------------------------------------
# _normalize_attachments
# ---------------------------------------------------------------------------

class TestNormalizeAttachments:
    def test_empty_list(self):
        assert EmailNotifier._normalize_attachments([]) == []

    def test_none_returns_empty(self):
        assert EmailNotifier._normalize_attachments(None) == []

    def test_valid_attachment(self):
        attachments = [{"filename": "report.pdf", "content": b"pdfdata"}]
        result = EmailNotifier._normalize_attachments(attachments)
        assert len(result) == 1
        assert result[0]["filename"] == "report.pdf"
        assert result[0]["content"] == b"pdfdata"
        assert "pdf" in result[0]["mimetype"]

    def test_string_content_encoded(self):
        attachments = [{"filename": "note.txt", "content": "hello"}]
        result = EmailNotifier._normalize_attachments(attachments)
        assert result[0]["content"] == b"hello"

    def test_bytearray_content_converted(self):
        attachments = [{"filename": "data.bin", "content": bytearray(b"bytes")}]
        result = EmailNotifier._normalize_attachments(attachments)
        assert isinstance(result[0]["content"], bytes)

    def test_missing_filename_skipped(self):
        attachments = [{"content": b"data"}]
        result = EmailNotifier._normalize_attachments(attachments)
        assert result == []

    def test_non_dict_item_skipped(self):
        result = EmailNotifier._normalize_attachments(["not-a-dict"])
        assert result == []

    def test_custom_mimetype_respected(self):
        attachments = [{"filename": "audio.ogg", "content": b"audio", "mimetype": "audio/ogg"}]
        result = EmailNotifier._normalize_attachments(attachments)
        assert result[0]["mimetype"] == "audio/ogg"

    def test_unknown_extension_defaults_to_octet_stream(self):
        attachments = [{"filename": "file.unknownxyz", "content": b"data"}]
        result = EmailNotifier._normalize_attachments(attachments)
        assert result[0]["mimetype"] == "application/octet-stream"

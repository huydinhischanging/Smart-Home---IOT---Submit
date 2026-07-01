import base64
import logging
import mimetypes
import os
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr

import requests

from app.domain.ports.email_notifier import EmailNotifierPort

logger = logging.getLogger(__name__)


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class EmailNotifier(EmailNotifierPort):
    def __init__(self):
        self.host = os.environ.get("SMTP_HOST", "").strip()
        self.port = int(os.environ.get("SMTP_PORT", "587") or "587")
        self.username = os.environ.get("SMTP_USERNAME", "").strip()
        self.password = (
            os.environ.get("SMTP_PASSWORD", "").strip()
            or os.environ.get("SMTP_APP_PASSWORD", "").strip()
        )
        self.use_tls = _truthy_env("SMTP_USE_TLS", default=True)
        self.use_ssl = _truthy_env("SMTP_USE_SSL", default=False)
        self.timeout = int(os.environ.get("SMTP_TIMEOUT", "20") or "20")
        self.from_email = os.environ.get("SMTP_FROM_EMAIL", self.username).strip()
        self.from_name = os.environ.get("SMTP_FROM_NAME", "Smart Home Alert").strip()
        self.default_recipients = self._parse_recipients(os.environ.get("ALERT_RECIPIENTS", ""))
        self.brevo_api_key = os.environ.get("BREVO_API_KEY", "").strip()
        self.brevo_api_url = os.environ.get("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email").strip()

    @staticmethod
    def _parse_recipients(raw) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, (list, tuple, set)):
            values = raw
        else:
            values = str(raw).replace(";", ",").split(",")
        recipients = []
        seen = set()
        for value in values:
            email = str(value or "").strip()
            if not email or "@" not in email:
                continue
            lowered = email.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            recipients.append(email)
        return recipients

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.host and self.port and self.username and self.password and self.from_email)

    @property
    def brevo_enabled(self) -> bool:
        return bool(self.brevo_api_key and self.from_email)

    @property
    def enabled(self) -> bool:
        return self.smtp_enabled or self.brevo_enabled

    @property
    def provider(self) -> str:
        if self.smtp_enabled:
            return "smtp"
        if self.brevo_enabled:
            return "brevo"
        return "none"

    def configuration_status(self) -> dict:
        smtp_missing = []
        if not self.host:
            smtp_missing.append("SMTP_HOST")
        if not self.username:
            smtp_missing.append("SMTP_USERNAME")
        if not self.password:
            smtp_missing.append("SMTP_PASSWORD")
        if not self.from_email:
            smtp_missing.append("SMTP_FROM_EMAIL")

        brevo_missing = []
        if not self.brevo_api_key:
            brevo_missing.append("BREVO_API_KEY")
        if not self.from_email:
            brevo_missing.append("SMTP_FROM_EMAIL")

        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "use_tls": self.use_tls,
            "use_ssl": self.use_ssl,
            "timeout": self.timeout,
            "default_recipients": list(self.default_recipients),
            "smtp_enabled": self.smtp_enabled,
            "smtp_missing": smtp_missing,
            "brevo_enabled": self.brevo_enabled,
            "brevo_api_url": self.brevo_api_url,
            "brevo_missing": brevo_missing,
            "missing": [] if self.enabled else sorted(set(smtp_missing + brevo_missing)),
        }

    def resolve_recipients(self, user_email=None, extra=None, include_default_recipients: bool = False) -> list[str]:
        recipients = []
        if user_email:
            recipients.append(user_email)
        if include_default_recipients:
            recipients.extend(self.default_recipients)
        recipients.extend(self._parse_recipients(extra))
        return self._parse_recipients(recipients)

    @staticmethod
    def _normalize_attachments(attachments) -> list[dict]:
        normalized = []
        for item in attachments or []:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename", "")).strip()
            content = item.get("content")
            if not filename or content is None:
                continue
            if isinstance(content, str):
                content = content.encode("utf-8")
            elif isinstance(content, bytearray):
                content = bytes(content)
            elif not isinstance(content, bytes):
                content = bytes(content)

            mimetype = str(item.get("mimetype", "")).strip() or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            normalized.append({
                "filename": filename,
                "content": content,
                "mimetype": mimetype,
            })
        return normalized

    def send_message(self, subject: str, body: str, recipients=None, attachments=None, html_body: str | None = None) -> dict:
        resolved = self._parse_recipients(recipients)
        normalized_attachments = self._normalize_attachments(attachments)
        if not resolved:
            return {
                "sent": False,
                "reason": "no-recipients",
                "recipients": [],
            }
        if not self.enabled:
            logger.warning("EmailNotifier is disabled: SMTP configuration is incomplete.")
            return {
                "sent": False,
                "reason": "email-not-configured",
                "recipients": resolved,
            }

        if self.smtp_enabled:
            return self._send_via_smtp(
                subject=subject,
                body=body,
                recipients=resolved,
                attachments=normalized_attachments,
                html_body=html_body,
            )

        if self.brevo_enabled:
            return self._send_via_brevo(
                subject=subject,
                body=body,
                recipients=resolved,
                attachments=normalized_attachments,
                html_body=html_body,
            )

        return {
            "sent": False,
            "reason": "email-not-configured",
            "recipients": resolved,
        }

    def send_async(self, subject: str, body: str, recipients=None, attachments=None, html_body: str | None = None) -> None:
        """Fire-and-forget: send email in a background daemon thread.

        The current request returns immediately.  Delivery result is only logged —
        use ``send_message`` (synchronous) when you need the return value in-band.
        """
        def _worker():
            try:
                result = self.send_message(
                    subject=subject,
                    body=body,
                    recipients=recipients,
                    attachments=attachments,
                    html_body=html_body,
                )
                if result.get("sent"):
                    logger.info("[email_async] sent OK → %s", result.get("recipients"))
                else:
                    logger.warning("[email_async] not sent: %s", result.get("reason"))
            except Exception as exc:  # pragma: no cover
                logger.error("[email_async] unhandled error: %s", exc, exc_info=True)

        t = threading.Thread(target=_worker, daemon=True, name="email-sender")
        t.start()

    def _send_via_smtp(self, subject: str, body: str, recipients: list[str], attachments: list[dict], html_body: str | None = None) -> dict:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((self.from_name, self.from_email))
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")
        for attachment in attachments:
            maintype, subtype = attachment["mimetype"].split("/", 1)
            msg.add_attachment(
                attachment["content"],
                maintype=maintype,
                subtype=subtype,
                filename=attachment["filename"],
            )

        try:
            if self.use_ssl:
                with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout) as smtp:
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                    smtp.ehlo()
                    if self.use_tls:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(self.username, self.password)
                    smtp.send_message(msg)
            logger.info("Email sent via SMTP to %d recipient(s): %s", len(recipients), recipients)
            return {
                "sent": True,
                "reason": "ok",
                "provider": "smtp",
                "recipients": recipients,
            }
        except Exception as exc:
            logger.error("Failed to send email via SMTP: %s", exc, exc_info=True)
            return {
                "sent": False,
                "reason": str(exc),
                "provider": "smtp",
                "recipients": recipients,
            }

    def _send_via_brevo(self, subject: str, body: str, recipients: list[str], attachments: list[dict], html_body: str | None = None) -> dict:
        payload = {
            "sender": {"email": self.from_email, "name": self.from_name},
            "to": [{"email": recipient} for recipient in recipients],
            "subject": subject,
            "textContent": body,
        }
        if html_body:
            payload["htmlContent"] = html_body
        if attachments:
            payload["attachment"] = [
                {
                    "name": attachment["filename"],
                    "content": base64.b64encode(attachment["content"]).decode("ascii"),
                }
                for attachment in attachments
            ]
        headers = {
            "accept": "application/json",
            "api-key": self.brevo_api_key,
            "content-type": "application/json",
        }

        try:
            response = requests.post(
                self.brevo_api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if 200 <= response.status_code < 300:
                logger.info("Email sent via Brevo to %d recipient(s): %s", len(recipients), recipients)
                return {
                    "sent": True,
                    "reason": "ok",
                    "provider": "brevo",
                    "recipients": recipients,
                }

            logger.error("Brevo send failed: HTTP %s %s", response.status_code, response.text)
            return {
                "sent": False,
                "reason": f"HTTP {response.status_code}",
                "provider": "brevo",
                "recipients": recipients,
            }
        except Exception as exc:
            logger.error("Failed to send email via Brevo: %s", exc, exc_info=True)
            return {
                "sent": False,
                "reason": str(exc),
                "provider": "brevo",
                "recipients": recipients,
            }
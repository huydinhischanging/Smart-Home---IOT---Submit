from abc import ABC, abstractmethod


class EmailNotifierPort(ABC):
    """Abstract port for sending transactional email messages.

    Concrete adapters (SMTP, Brevo API, etc.) live in app/gateways/ and
    must inherit from this class so the domain layer never depends on a
    specific email transport.
    """

    @abstractmethod
    def send_message(
        self,
        subject: str,
        body: str,
        recipients=None,
        attachments=None,
        html_body: str | None = None,
    ) -> dict:
        """Send an email.  Returns a dict with at least ``{"sent": bool}``."""

    @abstractmethod
    def resolve_recipients(
        self,
        user_email=None,
        extra=None,
        include_default_recipients: bool = False,
    ) -> list[str]:
        """Resolve the final recipient list for a notification."""

    @abstractmethod
    def configuration_status(self) -> dict:
        """Return a dict describing the current email provider configuration."""

    def send_async(
        self,
        subject: str,
        body: str,
        recipients=None,
        attachments=None,
        html_body: str | None = None,
    ) -> None:
        """Send an email in a background daemon thread (fire-and-forget).

        Default implementation falls back to synchronous ``send_message`` so
        concrete adapters that do not override this still work correctly.
        Concrete gateways should override for true non-blocking behaviour.
        """
        self.send_message(
            subject=subject,
            body=body,
            recipients=recipients,
            attachments=attachments,
            html_body=html_body,
        )

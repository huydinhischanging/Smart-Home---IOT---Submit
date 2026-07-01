import argparse
import json
import os
import sys
from datetime import datetime


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Importing settings loads backend/.env when python-dotenv is available.
from app.config import settings as _settings  # noqa: F401
from app.gateways.email_notifier import EmailNotifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check SMTP configuration or send a controlled test email.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only print SMTP configuration status without sending email.",
    )
    parser.add_argument(
        "--to",
        dest="recipients",
        action="append",
        default=[],
        help="Recipient email address. Repeat to add multiple recipients.",
    )
    parser.add_argument(
        "--subject",
        default="SMTP Test: Smart Home Elderly Care",
        help="Subject line for the test email.",
    )
    parser.add_argument(
        "--body",
        default="",
        help="Optional plain-text body. A default body is generated when omitted.",
    )
    parser.add_argument(
        "--include-default-recipients",
        action="store_true",
        help="Include ALERT_RECIPIENTS from the environment in the send target list.",
    )
    parser.add_argument(
        "--provider",
        choices=["auto", "smtp", "brevo"],
        default="auto",
        help="Validate intent against a specific provider mode. Sending still follows configured availability.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    notifier = EmailNotifier()
    status = notifier.configuration_status()

    if args.provider != "auto" and status["provider"] not in {args.provider, "none"}:
        print(
            json.dumps(
                {
                    "success": False,
                    "message": f"Configured provider is '{status['provider']}', not '{args.provider}'.",
                    "status": status,
                },
                indent=2,
            )
        )
        return 3

    if args.check:
        print(json.dumps(status, indent=2))
        return 0 if status["enabled"] else 1

    recipients = notifier.resolve_recipients(
        extra=args.recipients,
        include_default_recipients=args.include_default_recipients,
    )

    if not recipients:
        print(
            json.dumps(
                {
                    "success": False,
                    "message": "No recipients resolved. Pass --to or use --include-default-recipients.",
                    "status": status,
                },
                indent=2,
            )
        )
        return 2

    body = args.body.strip() or (
        "This is a controlled SMTP test from the Smart Home Elderly Care backend.\n\n"
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Backend directory: {BACKEND_DIR}\n"
        f"Recipients: {', '.join(recipients)}\n"
    )

    result = notifier.send_message(
        subject=args.subject,
        body=body,
        recipients=recipients,
    )
    print(
        json.dumps(
            {
                "success": bool(result.get("sent")),
                "delivery": result,
                "status": status,
            },
            indent=2,
        )
    )
    return 0 if result.get("sent") else 1


if __name__ == "__main__":
    raise SystemExit(main())
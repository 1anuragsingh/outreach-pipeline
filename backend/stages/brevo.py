import time
from pathlib import Path

import requests
from rich.console import Console
from rich.table import Table

from config import BREVO_API_KEY, SENDER_COMPANY, SENDER_EMAIL, SENDER_NAME
from utils.logger import logger

_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "email.txt"
_RATE_DELAY = 2.0

_console = Console()


def _load_template() -> tuple[str, str]:
    """Parse templates/email.txt into (subject_template, body_template)."""
    text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    first_line, _, rest = text.partition("\n")
    subject = first_line.removeprefix("Subject:").strip()
    body = rest.strip()
    return subject, body


def _render(template: str, contact: dict) -> str:
    company = contact.get("company") or contact.get("domain", "").split(".")[0].capitalize()
    return template.format(
        name=contact.get("name", ""),
        title=contact.get("title", ""),
        company=company,
        sender_name=SENDER_NAME,
        sender_company=SENDER_COMPANY,
    )


def _send_one(subject: str, body: str, contact: dict) -> None:
    """POST a single transactional email to Brevo. Raises Exception on failure."""
    response = requests.post(
        _ENDPOINT,
        json={
            "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
            "to": [{"name": contact.get("name", ""), "email": contact["email"]}],
            "subject": subject,
            "textContent": body,
        },
        headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
        timeout=30,
    )
    if not response.ok:
        try:
            msg = response.json().get("message", response.text)
        except Exception:
            msg = response.text
        raise Exception(f"HTTP {response.status_code}: {msg}")


def send_emails(contacts: list[dict], dry_run: bool = False) -> dict:
    """Send personalised outreach emails via Brevo with a pre-send safety checkpoint."""
    subject_tpl, body_tpl = _load_template()

    # ── Safety checkpoint ────────────────────────────────────────────────────
    table = Table(
        title="[bold]Outreach Preview[/]",
        border_style="cyan",
        header_style="bold cyan",
    )
    table.add_column("Name", style="bold white", no_wrap=True)
    table.add_column("Title", style="dim")
    table.add_column("Company")
    table.add_column("Email", style="green")

    for contact in contacts:
        company = contact.get("company") or contact.get("domain", "")
        table.add_row(
            contact.get("name", ""),
            contact.get("title", ""),
            company,
            contact.get("email", ""),
        )

    _console.print()
    _console.print(table)
    n = len(contacts)
    _console.print(
        f"\n[bold]Total:[/] {n} email{'s' if n != 1 else ''} will be sent"
    )

    # ── Dry-run: preview rendered emails, no prompt, no send ─────────────────
    if dry_run:
        _console.print("\n[bold yellow]DRY RUN — skipping confirmation and send.[/]\n")
        for contact in contacts:
            subject = _render(subject_tpl, contact)
            body = _render(body_tpl, contact)
            email = contact.get("email", "")
            _console.rule(f"[dim]To: {email}[/]")
            _console.print(f"[bold]Subject:[/] {subject}\n")
            _console.print(body)
        _console.print()
        return {"sent": 0, "failed": 0}

    # ── Confirmation prompt ───────────────────────────────────────────────────
    _console.print()
    answer = _console.input("[bold yellow]Confirm send? (yes/no):[/] ").strip().lower()
    if answer != "yes":
        _console.print("\n[bold red]Aborted. No emails sent.[/]")
        return {"sent": 0, "failed": 0}

    # ── Send loop ─────────────────────────────────────────────────────────────
    _console.print()
    sent = 0
    failed = 0
    total = len(contacts)

    for i, contact in enumerate(contacts, start=1):
        name = contact.get("name", "unknown")
        email = contact.get("email", "")
        subject = _render(subject_tpl, contact)
        body = _render(body_tpl, contact)

        try:
            _send_one(subject, body, contact)
            logger.info("Brevo: Sent to %s <%s>", name, email)
            sent += 1
        except Exception as exc:
            logger.error("Brevo: Failed for %s <%s> — %s", name, email, exc)
            failed += 1

        if i < total:
            time.sleep(_RATE_DELAY)

    # ── Final summary ─────────────────────────────────────────────────────────
    _console.print()
    _console.print(f"[bold green]{sent} sent[/], [bold red]{failed} failed[/]")
    logger.info("Brevo: %d sent, %d failed", sent, failed)

    return {"sent": sent, "failed": failed}

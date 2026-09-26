"""Gmail-backed reply lifecycle; read status is independent of processing status."""

from datetime import datetime, timedelta, timezone
import re
from email import message_from_bytes
from email.utils import parseaddr

PROCESSED = "PulseK12-processed"
PROCESSING = "PulseK12-processing"
LEGACY = "PulseK12-legacy"
INITIALIZED = "PulseK12-tracking-initialized"


def require_ok(result, operation):
    status, data = result
    if status != "OK":
        raise RuntimeError(f"Gmail {operation} failed: {status}")
    return data


def search_uids(mail, criteria):
    data = require_ok(mail.uid("search", None, criteria), "search")
    return data[0].split() if data and data[0] else []


def set_label(mail, uid, label, add=True):
    operation = "+X-GM-LABELS" if add else "-X-GM-LABELS"
    require_ok(mail.uid("store", uid, operation, f'("{label}")'), "label update")


def window_start(summaries_data=None, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    generated_at = (summaries_data or {}).get("generated_at")
    if generated_at:
        generated = datetime.fromisoformat(generated_at)
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        cutoff = max(cutoff, generated)
    return cutoff


def find_pending(mail, sender, summaries_data=None):
    """Bootstrap old read mail once, then find unlabeled replies using stable UIDs."""
    if any(char in sender for char in '\r\n"\\'):
        raise ValueError("Invalid editor email address")
    require_ok(mail.select("INBOX"), "inbox selection")
    cutoff = window_start(summaries_data)
    base = f'FROM "{sender}" SINCE "{cutoff.strftime("%d-%b-%Y")}"'
    marker = require_ok(mail.list('""', INITIALIZED), "tracking label lookup")
    if not marker or marker == [None]:
        # Old versions used read status as their only receipt. Preserve that baseline.
        for label in (PROCESSED, PROCESSING, LEGACY):
            existing = require_ok(mail.list('""', label), "label lookup")
            if not existing or existing == [None]:
                require_ok(mail.create(label), "label creation")
        for uid in search_uids(mail, f'({base} SEEN)'):
            raw = fetch_reply(mail, uid, cutoff)
            if raw and parseaddr(message_from_bytes(raw).get("From", ""))[1].lower() == sender:
                set_label(mail, uid, LEGACY)
        require_ok(mail.create(INITIALIZED), "tracking initialization")

    uncertain = search_uids(mail, f'({base} X-GM-LABELS "{PROCESSING}" NOT X-GM-LABELS "{PROCESSED}")')
    if uncertain:
        raise RuntimeError("A previous send has an uncertain outcome. Review PulseK12-processing in Gmail before retrying.")
    criteria = f'({base} NOT X-GM-LABELS "{PROCESSED}" NOT X-GM-LABELS "{PROCESSING}" NOT X-GM-LABELS "{LEGACY}")'
    return cutoff, search_uids(mail, criteria)


def fetch_reply(mail, uid, cutoff):
    data = require_ok(mail.uid("fetch", uid, "(BODY.PEEK[] INTERNALDATE)"), "message fetch")
    for item in data:
        if not isinstance(item, tuple):
            continue
        metadata, raw = item
        match = re.search(rb'INTERNALDATE "([^"]+)"', metadata)
        if not match:
            raise RuntimeError("Gmail did not return the message arrival date")
        received = datetime.strptime(match.group(1).decode("ascii"), "%d-%b-%Y %H:%M:%S %z")
        return raw if received >= cutoff else None
    raise RuntimeError("Gmail returned no message body")


def current_menu_subject(subject, summaries_data):
    """Do not apply last week's numbers to this week's menu."""
    generated_at = (summaries_data or {}).get("generated_at")
    if not generated_at:
        return False
    generated = datetime.fromisoformat(generated_at)
    expected = f'Week of {generated.strftime("%b %d, %Y")}'.lower()
    return "pulsek12" in subject.lower() and expected in subject.lower()


def start_send(mail, uid):
    # Hold before SMTP: interrupted/ambiguous sends require review instead of duplicates.
    set_label(mail, uid, PROCESSING)


def finish_send(mail, uid):
    set_label(mail, uid, PROCESSED)
    set_label(mail, uid, PROCESSING, add=False)

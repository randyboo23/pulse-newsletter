#!/usr/bin/env python3
"""
Email listener for PulseK12 newsletter finalization.
Monitors Gmail for replies to menu emails and triggers finalization.

Runs on schedule via GitHub Actions every 15 minutes on Fridays/Saturdays.
"""

import sys
import os
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.finalize import finalize_issue, load_summaries, SUMMARIES_FILE


# IMAP configuration for Gmail
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993


def get_email_credentials() -> tuple[str, str]:
    """Get email credentials from environment (same as SMTP for Gmail)."""
    # Use same credentials as SMTP sending (Gmail uses same creds for IMAP)
    email_user = os.getenv("SMTP_USER")
    email_pass = os.getenv("SMTP_PASSWORD")

    if not email_user or not email_pass:
        raise ValueError(
            "SMTP_USER and SMTP_PASSWORD must be set in environment. "
            "For Gmail, use an App Password."
        )

    return email_user, email_pass


def get_target_sender() -> str:
    """Get the email address we're listening for replies from."""
    email_to = os.getenv("EMAIL_TO")
    if not email_to:
        raise ValueError("EMAIL_TO must be set in environment")
    return email_to.lower()


def connect_to_gmail() -> imaplib.IMAP4_SSL:
    """Connect to Gmail IMAP server."""
    email_user, email_pass = get_email_credentials()

    print(f"Connecting to Gmail IMAP as {email_user}...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(email_user, email_pass)
    print("  Connected successfully")

    return mail


def decode_email_subject(subject) -> str:
    """Decode email subject which may be encoded."""
    if subject is None:
        return ""

    decoded_parts = decode_header(subject)
    subject_str = ""

    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            subject_str += part.decode(encoding or "utf-8", errors="ignore")
        else:
            subject_str += part

    return subject_str


def get_email_body(msg) -> str:
    """Extract plain text body from email message."""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            # Get plain text parts
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="ignore")
                except Exception:
                    pass
    else:
        # Not multipart - get payload directly
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="ignore")
        except Exception:
            body = str(msg.get_payload())

    return body


def extract_reply_content(body: str) -> str:
    """
    Extract only the new reply content, ignoring quoted original email.

    Stops at common quote markers like:
    - "On ... wrote:"
    - Lines starting with ">"
    - "---------- Forwarded message"
    - Gmail's "On Mon, Jan 5, 2026 at..." pattern
    """
    lines = body.split('\n')
    reply_lines = []

    for line in lines:
        line_stripped = line.strip()

        # Stop at quote markers
        if line_stripped.startswith('>'):
            break
        if re.match(r'^On .+ wrote:$', line_stripped):
            break
        if re.match(r'^On \w+, \w+ \d+, \d{4} at', line_stripped):
            break
        if '---------- Forwarded message' in line_stripped:
            break
        if line_stripped.startswith('From:') and '@' in line_stripped:
            break
        if re.match(r'^-{3,}.*Original Message.*-{3,}$', line_stripped, re.IGNORECASE):
            break

        reply_lines.append(line)

    return '\n'.join(reply_lines)


def parse_selection_from_body(body: str) -> list[int]:
    """
    Parse article numbers from email body.

    Handles formats like:
    - "1, 3, 5, 7"
    - "1,3,5,7"
    - "I want 1, 3, 5, and 7"
    - "Numbers 1 3 5 7 please"
    """
    # Only look at the reply content, not quoted original
    reply_content = extract_reply_content(body)

    # Extract all numbers from the reply
    numbers = re.findall(r'\b(\d{1,2})\b', reply_content)

    # Filter to reasonable article numbers (1-20)
    valid_numbers = [int(n) for n in numbers if 1 <= int(n) <= 20]

    # Remove duplicates while preserving order
    seen = set()
    unique_numbers = []
    for n in valid_numbers:
        if n not in seen:
            seen.add(n)
            unique_numbers.append(n)

    return unique_numbers


def is_menu_reply(subject: str) -> bool:
    """Check if this email is a reply to a PulseK12 menu email."""
    subject_lower = subject.lower()

    # Check for reply indicators and PulseK12 reference
    is_reply = subject_lower.startswith("re:") or subject_lower.startswith("fwd:")
    has_pulse = "pulsek12" in subject_lower or "pulse" in subject_lower
    has_menu = "menu" in subject_lower

    return is_reply and (has_pulse or has_menu)


def check_for_replies(mail: imaplib.IMAP4_SSL) -> list[dict]:
    """
    Check for unread reply emails from target sender.

    Returns list of dicts with email info and parsed selections.
    """
    target_sender = get_target_sender()
    replies = []

    # Select inbox
    mail.select("INBOX")

    # Search for unread emails from target sender
    search_criteria = f'(UNSEEN FROM "{target_sender}")'
    print(f"Searching for unread emails from {target_sender}...")

    status, messages = mail.search(None, search_criteria)

    if status != "OK":
        print("  Search failed")
        return replies

    email_ids = messages[0].split()
    print(f"  Found {len(email_ids)} unread emails")

    for email_id in email_ids:
        status, msg_data = mail.fetch(email_id, "(RFC822)")

        if status != "OK":
            continue

        # Parse email
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_email_subject(msg.get("Subject", ""))
        from_addr = msg.get("From", "").lower()
        body = get_email_body(msg)

        print(f"\n  Checking email: {subject[:50]}...")
        print(f"    From: {from_addr}")

        # Check if this is a reply to our menu email
        if not is_menu_reply(subject):
            print("    Skipping: Not a menu reply")
            continue

        # Parse selection numbers from body
        selection = parse_selection_from_body(body)

        if not selection:
            print("    Skipping: No valid article numbers found")
            continue

        print(f"    Found selection: {selection}")

        replies.append({
            "email_id": email_id,
            "subject": subject,
            "from": from_addr,
            "body": body,
            "selection": selection
        })

    return replies


def mark_as_read(mail: imaplib.IMAP4_SSL, email_id: bytes) -> bool:
    """Mark an email as read."""
    try:
        mail.store(email_id, "+FLAGS", "\\Seen")
        return True
    except Exception as e:
        print(f"  Warning: Could not mark email as read: {e}")
        return False


def process_reply(reply: dict) -> dict:
    """Process a reply email and generate the final newsletter."""
    selection = reply["selection"]
    selection_str = ",".join(str(n) for n in selection)

    print(f"\nProcessing reply with selection: {selection_str}")

    # Use the finalize_issue function from finalize.py
    result = finalize_issue(selection_str, send_email=True)

    return result


def run_listener() -> dict:
    """
    Main listener function.

    Checks for replies and processes them.
    Returns dict with results.
    """
    print("=" * 60)
    print("PulseK12 Email Listener")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    results = {
        "started_at": datetime.now().isoformat(),
        "replies_found": 0,
        "replies_processed": 0,
        "errors": []
    }

    # Check if we have summaries to work with
    print("\n[1/3] Checking for saved summaries...")
    if not SUMMARIES_FILE.exists():
        print("  No summaries file found. Run the main pipeline first.")
        results["errors"].append("No summaries file found")
        return results

    try:
        summaries = load_summaries()
        print(f"  Found {len(summaries)} summaries from last pipeline run")
    except Exception as e:
        print(f"  Error loading summaries: {e}")
        results["errors"].append(str(e))
        return results

    # Connect to Gmail
    print("\n[2/3] Connecting to Gmail...")
    try:
        mail = connect_to_gmail()
    except Exception as e:
        print(f"  Connection failed: {e}")
        results["errors"].append(f"IMAP connection failed: {e}")
        return results

    # Check for replies
    print("\n[3/3] Checking for replies...")
    try:
        replies = check_for_replies(mail)
        results["replies_found"] = len(replies)
    except Exception as e:
        print(f"  Error checking replies: {e}")
        results["errors"].append(str(e))
        mail.logout()
        return results

    if not replies:
        print("\nNo menu replies found. Nothing to process.")
        mail.logout()
        return results

    # Process each reply
    for reply in replies:
        print(f"\n{'=' * 40}")
        print(f"Processing reply: {reply['subject'][:40]}...")

        try:
            process_result = process_reply(reply)

            if process_result.get("success"):
                # Mark as read to prevent reprocessing
                mark_as_read(mail, reply["email_id"])
                results["replies_processed"] += 1
                print("  Successfully processed and marked as read")
            else:
                error = process_result.get("error", "Unknown error")
                print(f"  Processing failed: {error}")
                results["errors"].append(error)

        except Exception as e:
            print(f"  Error processing reply: {e}")
            results["errors"].append(str(e))

    # Cleanup
    mail.logout()

    # Summary
    print("\n" + "=" * 60)
    print("Listener Complete!")
    print(f"  Replies found: {results['replies_found']}")
    print(f"  Replies processed: {results['replies_processed']}")
    if results["errors"]:
        print(f"  Errors: {len(results['errors'])}")
    print("=" * 60)

    results["completed_at"] = datetime.now().isoformat()
    return results


def main():
    """CLI entry point."""
    result = run_listener()

    # Exit with error code if no replies processed but some were found
    if result["replies_found"] > 0 and result["replies_processed"] == 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

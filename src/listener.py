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
load_dotenv(override=True)

from src.finalize import finalize_issue, load_summaries, SUMMARIES_FILE


# IMAP configuration for Gmail
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993

# URL submission configuration
MAX_URLS_PER_REQUEST = 10
URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')


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

    # Remove URLs before parsing numbers (URLs contain numbers that aren't selections)
    content_without_urls = URL_PATTERN.sub('', reply_content)

    # Extract all numbers from the cleaned content
    numbers = re.findall(r'\b(\d{1,2})\b', content_without_urls)

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


def extract_urls_from_body(body: str) -> list[str]:
    """
    Extract valid URLs from email body (one per line expected).

    Args:
        body: Email body text

    Returns:
        List of unique, valid URLs (max MAX_URLS_PER_REQUEST)
    """
    # Only look at reply content, not quoted original
    reply_content = extract_reply_content(body)

    # Find all URLs
    urls = URL_PATTERN.findall(reply_content)

    # Clean URLs (remove trailing punctuation that might be captured)
    cleaned = []
    for url in urls:
        # Strip trailing punctuation
        url = url.rstrip('.,;:!?)\'"')
        if url and url not in cleaned:
            cleaned.append(url)

    return cleaned[:MAX_URLS_PER_REQUEST]


def parse_email_content(body: str) -> dict:
    """
    Parse email body for both menu selections AND URLs.

    Returns dict with 'selections' (list of ints) and 'urls' (list of strings).
    Both can be present in the same email.
    """
    selections = parse_selection_from_body(body)
    urls = extract_urls_from_body(body)

    return {
        "selections": selections,
        "urls": urls,
        "has_selections": len(selections) > 0,
        "has_urls": len(urls) > 0
    }


def get_domain_from_url(url: str) -> str:
    """Extract domain name from URL for source attribution."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remove www. prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return "Unknown"


def is_international_url(url: str) -> tuple[bool, str]:
    """
    Check if URL is from an international (non-US) source.

    Returns:
        Tuple of (is_international, reason)
    """
    from src.categorizer import INTERNATIONAL_DOMAINS, INTERNATIONAL_COUNTRIES

    domain = get_domain_from_url(url).lower()

    # Check domain TLDs and patterns
    for intl_domain in INTERNATIONAL_DOMAINS:
        if intl_domain in domain:
            return True, f"international domain: {intl_domain}"

    # Check for international country indicators in domain
    for country in INTERNATIONAL_COUNTRIES:
        if country in domain:
            return True, f"international indicator: {country}"

    return False, ""


def check_for_replies(mail: imaplib.IMAP4_SSL) -> list[dict]:
    """
    Check for unread emails from target sender.

    Returns list of dicts with email info, parsed selections AND URLs.
    An email can contain both menu selections and URLs to process together.
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
        # Use BODY.PEEK[] to fetch without marking as read
        # RFC822 implicitly marks messages as \Seen
        status, msg_data = mail.fetch(email_id, "(BODY.PEEK[])")

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

        # Debug: show extracted reply content
        reply_content = extract_reply_content(body)
        print(f"    Body length: {len(body)} chars, Reply content: {len(reply_content)} chars")
        if reply_content.strip():
            # Show first 200 chars of reply content for debugging
            preview = reply_content.strip()[:200].replace('\n', ' ')
            print(f"    Reply preview: {preview}")
        else:
            print("    Reply preview: (empty after quote removal)")

        # Parse both selections and URLs from the email
        parsed = parse_email_content(body)

        # Log what we found
        if parsed["has_selections"]:
            print(f"    Found selections: {parsed['selections']}")
        if parsed["has_urls"]:
            print(f"    Found URLs: {len(parsed['urls'])}")

        # Skip if email has neither selections nor URLs
        if not parsed["has_selections"] and not parsed["has_urls"]:
            # Check if it's at least a menu reply (might just be text response)
            if is_menu_reply(subject):
                print("    Skipping: Menu reply but no selections or URLs found")
            else:
                print("    Skipping: No selections or URLs found")
            continue

        replies.append({
            "email_id": email_id,
            "subject": subject,
            "from": from_addr,
            "body": body,
            "selections": parsed["selections"],
            "urls": parsed["urls"],
            "has_selections": parsed["has_selections"],
            "has_urls": parsed["has_urls"]
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


def process_url_submission(urls: list[str]) -> dict:
    """
    Process a list of URLs: scrape and summarize each.

    Args:
        urls: List of URLs to process

    Returns:
        Dict with 'success', 'results', 'failed', 'truncated'
    """
    import time
    from src.scraper import scrape_article, get_firecrawl_client, SCRAPE_DELAY_SECONDS
    from src.summarizer import summarize_article
    from src.feeds import resolve_google_news_url

    results = []
    failed = []
    truncated = len(urls) > MAX_URLS_PER_REQUEST
    urls_to_process = urls[:MAX_URLS_PER_REQUEST]

    print(f"Processing {len(urls_to_process)} URLs for on-demand summarization...")

    try:
        firecrawl_client = get_firecrawl_client()
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to initialize Firecrawl: {e}",
            "results": [],
            "failed": [(url, "Service unavailable") for url in urls_to_process],
            "truncated": truncated
        }

    for i, url in enumerate(urls_to_process):
        print(f"  [{i+1}/{len(urls_to_process)}] Processing: {url[:60]}...")

        # Resolve Google News URLs if needed
        resolved_url = url
        if "news.google.com" in url:
            try:
                resolved_url = resolve_google_news_url(url) or url
                if resolved_url != url:
                    print(f"    Resolved to: {resolved_url[:60]}...")
            except Exception as e:
                print(f"    URL resolution failed: {e}")

        # Check for international sources (US-only newsletter)
        is_intl, intl_reason = is_international_url(resolved_url)
        if is_intl:
            print(f"    Skipping: {intl_reason}")
            failed.append((url, f"International source blocked ({intl_reason})"))
            continue

        # Scrape article
        scrape_result = scrape_article(resolved_url, firecrawl_client)

        if not scrape_result["success"]:
            error_msg = scrape_result.get("error", "Unknown error")[:50]
            print(f"    Failed to scrape: {error_msg}")
            failed.append((url, f"Scrape failed: {error_msg}"))
            continue

        # Build article dict for summarizer
        article = {
            "title": scrape_result.get("title") or "Article",
            "url": url,
            "resolved_url": resolved_url,
            "source": get_domain_from_url(resolved_url),
            "full_content": scrape_result["content"],
            "category": "research"  # Default category for on-demand
        }

        # Summarize
        try:
            summary = summarize_article(article)
        except Exception as e:
            print(f"    Summarization error: {e}")
            results.append({
                "url": url,
                "headline": article["title"],
                "summary": "(Summary generation failed)",
                "source": article["source"],
                "success": False
            })
            continue

        if not summary.get("success"):
            print(f"    Failed to summarize: {summary.get('error')}")
            results.append({
                "url": url,
                "headline": article["title"],
                "summary": "(Summary generation failed)",
                "source": article["source"],
                "success": False
            })
        else:
            print(f"    Success: {summary['headline'][:40]}...")
            results.append({
                "url": url,
                "headline": summary["headline"],
                "summary": summary["summary"],
                "source": article["source"],
                "success": True
            })

        # Rate limiting delay (skip on last URL)
        if i < len(urls_to_process) - 1:
            time.sleep(SCRAPE_DELAY_SECONDS)

    return {
        "success": True,
        "results": results,
        "failed": failed,
        "truncated": truncated,
        "processed_count": len(results),
        "failed_count": len(failed)
    }


def format_url_summary_response(process_result: dict) -> str:
    """
    Format the URL summarization results as an email response.

    Args:
        process_result: Dict from process_url_submission

    Returns:
        Formatted markdown email content
    """
    results = process_result.get("results", [])
    failed = process_result.get("failed", [])
    truncated = process_result.get("truncated", False)

    today = datetime.now()
    date_str = today.strftime("%B %d, %Y")

    output = f"""# PulseK12 On-Demand Summaries
**{date_str}**

Here are the summaries you requested:

---

"""

    # Add successful summaries
    for i, result in enumerate(results, 1):
        headline = result.get("headline", "Article")
        url = result.get("url", "#")
        summary_text = result.get("summary", "")
        source = result.get("source", "Unknown")

        output += f"""**{i}.** **[{headline}]({url})**

{summary_text}

*Source: {source}*

---

"""

    # Summary line
    success_count = sum(1 for r in results if r.get("success", False))
    output += f"\n*Processed {len(results)} URLs ({success_count} successful)."

    if failed:
        output += f" {len(failed)} URLs failed (see below).*\n\n"
        output += "**Failed URLs:**\n"
        for url, error in failed:
            display_url = url[:60] + "..." if len(url) > 60 else url
            output += f"- {display_url} - {error}\n"
    else:
        output += "*\n"

    if truncated:
        output += f"\n*Note: Only the first {MAX_URLS_PER_REQUEST} URLs were processed. Please send additional requests for more URLs.*\n"

    output += "\n---\n*Generated by PulseK12 Newsletter Engine*"

    return output


def send_url_summary_response(to_email: str, content: str, original_subject: str) -> dict:
    """
    Send the URL summary response email.

    Args:
        to_email: Recipient email
        content: Formatted response content
        original_subject: Original email subject for reply threading

    Returns:
        Dict with 'success', 'error'
    """
    from src.emailer import send_newsletter

    # Create reply subject
    if original_subject.lower().startswith("re:"):
        subject = original_subject
    else:
        subject = f"Re: {original_subject}"

    # Ensure it mentions PulseK12 for tracking
    if "pulsek12" not in subject.lower() and "pulse" not in subject.lower():
        subject = f"PulseK12 Summaries - {subject}"

    return send_newsletter(content, subject=subject, to_email=to_email)


def process_combined_reply(reply: dict, summaries_data: dict = None) -> dict:
    """
    Process a reply that may contain both menu selections AND URLs.

    Args:
        reply: Dict with 'selections' and 'urls' from check_for_replies
        summaries_data: Loaded summaries data (for menu selections)

    Returns:
        Dict with 'success', 'content', 'menu_count', 'url_count', 'error'
    """
    selections = reply.get("selections", [])
    urls = reply.get("urls", [])

    menu_summaries = []
    url_summaries = []
    failed_urls = []

    # Process menu selections if we have them and summaries are available
    if selections and summaries_data:
        saved_summaries = summaries_data.get("summaries", [])
        for num in selections:
            if 1 <= num <= len(saved_summaries):
                menu_summaries.append(saved_summaries[num - 1])
                print(f"    Added menu selection #{num}")

    # Process URLs if we have them
    if urls:
        url_result = process_url_submission(urls)
        url_summaries = url_result.get("results", [])
        failed_urls = url_result.get("failed", [])

    # Format combined response
    content = format_combined_response(
        menu_summaries=menu_summaries,
        url_summaries=url_summaries,
        failed_urls=failed_urls,
        local_themes=summaries_data.get("local_themes", []) if summaries_data else []
    )

    return {
        "success": True,
        "content": content,
        "menu_count": len(menu_summaries),
        "url_count": len(url_summaries),
        "failed_count": len(failed_urls)
    }


def format_combined_response(
    menu_summaries: list,
    url_summaries: list,
    failed_urls: list,
    local_themes: list
) -> str:
    """
    Format a combined response with both menu selections and URL summaries.
    """
    today = datetime.now()
    date_str = today.strftime("%B %d, %Y")

    output = f"""# PulseK12 Weekly Issue
**{date_str}**

"""

    item_num = 1

    # Add menu selections first (these are from the curated list)
    if menu_summaries:
        output += "## Selected Stories\n\n"
        for summary in menu_summaries:
            emoji = summary.get("category_emoji", "📰")
            headline = summary.get("headline", "Article")
            url = summary.get("source_url", "#")
            text = summary.get("summary", "")
            source = summary.get("source_name", "Unknown")

            output += f"""**{item_num}.** {emoji} **[{headline}]({url})**

{text}

*Source: {source}*

---

"""
            item_num += 1

    # Add URL summaries (on-demand requests)
    if url_summaries:
        if menu_summaries:
            output += "\n## Additional Stories\n\n"
        for result in url_summaries:
            headline = result.get("headline", "Article")
            url = result.get("url", "#")
            text = result.get("summary", "")
            source = result.get("source", "Unknown")

            output += f"""**{item_num}.** **[{headline}]({url})**

{text}

*Source: {source}*

---

"""
            item_num += 1

    # Add local themes if available
    if local_themes:
        output += "\n## Local Spotlight\n\n"
        for theme in local_themes:
            theme_name = theme.get("theme_title", theme.get("theme_name", "Local Story"))
            states = theme.get("states_mentioned", theme.get("states", []))
            theme_summary = theme.get("blurb", theme.get("summary", ""))

            states_str = ", ".join(states) if states else ""
            output += f"""**{theme_name}** ({states_str})

{theme_summary}

---

"""

    # Summary stats
    total = len(menu_summaries) + len(url_summaries)
    output += f"\n*Total stories: {total}"
    if menu_summaries and url_summaries:
        output += f" ({len(menu_summaries)} selected + {len(url_summaries)} on-demand)"
    output += "*\n"

    # Failed URLs if any
    if failed_urls:
        output += f"\n**Failed URLs ({len(failed_urls)}):**\n"
        for url, error in failed_urls:
            display_url = url[:60] + "..." if len(url) > 60 else url
            output += f"- {display_url} - {error}\n"

    output += "\n---\n*Generated by PulseK12 Newsletter Engine*"

    return output


def run_listener() -> dict:
    """
    Main listener function.

    Checks for emails with menu selections AND/OR URLs, processes both together.
    Returns dict with results.
    """
    print("=" * 60)
    print("PulseK12 Email Listener")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    results = {
        "started_at": datetime.now().isoformat(),
        "emails_found": 0,
        "emails_processed": 0,
        "total_selections": 0,
        "total_urls": 0,
        "errors": []
    }

    # Check if we have summaries (needed for menu selections)
    print("\n[1/3] Checking for saved summaries...")
    summaries_data = None
    if SUMMARIES_FILE.exists():
        try:
            summaries_data = load_summaries()
            summaries = summaries_data.get("summaries", [])
            local_themes = summaries_data.get("local_themes", [])
            print(f"  Found {len(summaries)} national summaries from last pipeline run")
            if local_themes:
                print(f"  Found {len(local_themes)} local themes")
        except Exception as e:
            print(f"  Warning: Error loading summaries: {e}")
            summaries_data = None
    else:
        print("  No summaries file found (menu selections won't work, URLs will)")

    # Connect to Gmail
    print("\n[2/3] Connecting to Gmail...")
    try:
        mail = connect_to_gmail()
    except Exception as e:
        print(f"  Connection failed: {e}")
        results["errors"].append(f"IMAP connection failed: {e}")
        return results

    # Check for replies
    print("\n[3/3] Checking for emails...")
    try:
        replies = check_for_replies(mail)
        results["emails_found"] = len(replies)
    except Exception as e:
        print(f"  Error checking emails: {e}")
        results["errors"].append(str(e))
        mail.logout()
        return results

    if not replies:
        print("\nNo actionable emails found. Nothing to process.")
        mail.logout()
        return results

    # Process each reply (may contain selections, URLs, or both)
    for reply in replies:
        print(f"\n{'=' * 40}")
        print(f"Processing: {reply['subject'][:50]}...")

        has_selections = reply.get("has_selections", False)
        has_urls = reply.get("has_urls", False)
        selections = reply.get("selections", [])
        urls = reply.get("urls", [])

        # Skip menu selections if no summaries available
        if has_selections and not summaries_data:
            print(f"  Warning: Ignoring {len(selections)} selections (no summaries file)")
            selections = []
            has_selections = False

        if not has_selections and not has_urls:
            print("  Skipping: Nothing to process")
            continue

        print(f"  Processing: {len(selections)} selections + {len(urls)} URLs")

        try:
            # Process combined reply
            process_result = process_combined_reply(reply, summaries_data)

            if process_result.get("success"):
                # Get sender email for reply
                from_addr = reply["from"]
                if "<" in from_addr and ">" in from_addr:
                    from_addr = from_addr.split("<")[1].split(">")[0]

                # Send response
                send_result = send_url_summary_response(
                    to_email=from_addr,
                    content=process_result["content"],
                    original_subject=reply["subject"]
                )

                if send_result.get("success"):
                    mark_as_read(mail, reply["email_id"])
                    results["emails_processed"] += 1
                    results["total_selections"] += process_result.get("menu_count", 0)
                    results["total_urls"] += process_result.get("url_count", 0)
                    print(f"  Success: {process_result.get('menu_count', 0)} selections + {process_result.get('url_count', 0)} URLs")
                    print("  Response sent and marked as read")
                else:
                    print(f"  Failed to send response: {send_result.get('error')}")
                    results["errors"].append(f"Email send failed: {send_result.get('error')}")
            else:
                error = process_result.get("error", "Unknown error")
                print(f"  Processing failed: {error}")
                results["errors"].append(error)

        except Exception as e:
            print(f"  Error processing: {e}")
            results["errors"].append(str(e))

    # Cleanup
    mail.logout()

    # Summary
    print("\n" + "=" * 60)
    print("Listener Complete!")
    print(f"  Emails found: {results['emails_found']}")
    print(f"  Emails processed: {results['emails_processed']}")
    print(f"  Total selections processed: {results['total_selections']}")
    print(f"  Total URLs processed: {results['total_urls']}")
    if results["errors"]:
        print(f"  Errors: {len(results['errors'])}")
    print("=" * 60)

    results["completed_at"] = datetime.now().isoformat()
    return results


def main():
    """CLI entry point."""
    result = run_listener()

    # Exit with error code if emails found but none processed
    if result.get("emails_found", 0) > 0 and result.get("emails_processed", 0) == 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

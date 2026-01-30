"""
Email delivery module using Gmail SMTP.
Sends the formatted newsletter menu via email.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)


def get_smtp_config() -> dict:
    """Get SMTP configuration from environment."""
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "to": os.getenv("EMAIL_TO"),
        "cc": os.getenv("EMAIL_CC"),
    }


def get_week_subject() -> str:
    """Generate subject line with current week date."""
    today = datetime.now()
    return f"PulseK12 Menu — Week of {today.strftime('%b %d, %Y')}"


def send_newsletter(
    markdown_content: str,
    subject: str = None,
    to_email: str = None,
    cc_email: str = None
) -> dict:
    """
    Send the newsletter via Gmail SMTP.

    Args:
        markdown_content: The formatted markdown newsletter content
        subject: Email subject (defaults to week-based subject)
        to_email: Recipient email (defaults to env EMAIL_TO)
        cc_email: CC email (defaults to env EMAIL_CC)

    Returns:
        Dict with 'success', 'message', 'error'
    """
    config = get_smtp_config()

    # Use defaults from config if not provided
    subject = subject or get_week_subject()
    to_email = to_email or config["to"]
    cc_email = cc_email or config["cc"]

    # Validate required config
    if not config["user"] or not config["password"]:
        return {
            "success": False,
            "message": "SMTP credentials not configured",
            "error": "Missing SMTP_USER or SMTP_PASSWORD"
        }

    if not to_email:
        return {
            "success": False,
            "message": "No recipient email configured",
            "error": "Missing EMAIL_TO"
        }

    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["user"]
        msg["To"] = to_email
        if cc_email:
            msg["Cc"] = cc_email

        # Add plain text part (markdown)
        text_part = MIMEText(markdown_content, "plain", "utf-8")
        msg.attach(text_part)

        # Build recipient list
        recipients = [to_email]
        if cc_email:
            recipients.append(cc_email)

        # Send via SMTP
        print(f"Connecting to {config['host']}:{config['port']}...")

        with smtplib.SMTP(config["host"], config["port"]) as server:
            server.starttls()
            server.login(config["user"], config["password"])
            server.sendmail(config["user"], recipients, msg.as_string())

        print(f"Email sent successfully to {to_email}" + (f" (cc: {cc_email})" if cc_email else ""))

        return {
            "success": True,
            "message": f"Newsletter sent to {to_email}",
            "error": None
        }

    except smtplib.SMTPAuthenticationError as e:
        return {
            "success": False,
            "message": "SMTP authentication failed",
            "error": f"Check your Gmail app password: {e}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": "Failed to send email",
            "error": str(e)
        }


def preview_email(markdown_content: str) -> None:
    """Print email preview to console."""
    subject = get_week_subject()
    config = get_smtp_config()

    print("=" * 60)
    print("EMAIL PREVIEW")
    print("=" * 60)
    print(f"From: {config['user']}")
    print(f"To: {config['to']}")
    print(f"Cc: {config['cc']}")
    print(f"Subject: {subject}")
    print("-" * 60)
    print(markdown_content)
    print("=" * 60)


if __name__ == "__main__":
    # Test email preview
    test_content = """# PulseK12 Weekly Menu

Here are this week's top stories for your review.

---

### 🧠 [AI Tutoring Tools Show Promise in Early Studies](https://example.com/ai)

**The Gist:** New research from RAND shows 45% of districts now use AI tutoring. Students using these tools 30 minutes daily showed 15% improvement in math scores.

**Why It Matters:** As districts look for scalable intervention solutions, AI tutoring could be a cost-effective complement to human instruction.

*Source: EdWeek*

---

### 📜 [New State Funding Formula Approved](https://example.com/funding)

**The Gist:** The state legislature passed a weighted funding formula that increases per-pupil spending for high-need students by 20%.

**Why It Matters:** This could mean significant budget increases for Title I schools in your district.

*Source: Chalkbeat*

---

*Reply to this email with your selections (or just hit reply and type the numbers).*
"""

    preview_email(test_content)

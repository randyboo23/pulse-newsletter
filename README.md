# PulseK12 Newsletter Automation Engine

Automated weekly newsletter generation for K-12 education news. Sends a menu of summarized articles for editorial review, then generates a Beehiiv-ready final issue based on the editor's selections.

## How It Works

### Friday Morning: Menu Generation
Every Friday at 6:00 AM CST, the system:

1. **Fetches** ~350 articles from Google News RSS feeds across 6 topic areas
2. **Filters** to ~170 relevant education articles (removes spam, off-topic, blocked sources)
3. **Deduplicates** and classifies into 8 categories
4. **Selects** a balanced menu of 20 articles with backups
5. **Scrapes** full content using Firecrawl API
6. **Summarizes** each article using Claude (3 sentences, PulseK12 voice)
7. **Emails** the formatted menu for editorial review

### Friday/Saturday: Reply Listener
Every 15 minutes on Fridays and Saturdays:

1. **Checks** Gmail for replies from the editor
2. **Parses** selected article numbers (e.g., "1, 3, 5, 7, 9")
3. **Generates** "This Week at a Glance" summary bullets
4. **Formats** final issue in Beehiiv-ready format
5. **Emails** the complete issue back to the editor

## Categories

| Emoji | Category | Topics |
|-------|----------|--------|
| 🧠 | AI & EdTech | AI tools, education technology, innovation |
| 📜 | Policy Watch | Legislation, funding, regulations |
| 🎓 | Teaching & Learning | Instruction, curriculum, literacy |
| 📊 | Research & Data | Studies, reports, findings |
| 🏫 | District Spotlight | Success stories, implementations |
| 🔒 | Safety & Privacy | School safety, data security, choice |
| 💚 | Student Wellness | Mental health, attendance, SEL |
| 👥 | Leadership | Admin insights, staffing |

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/randyboo23/pulse-newsletter.git
cd pulse-newsletter
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required secrets:
- `ANTHROPIC_API_KEY` - Get from [console.anthropic.com](https://console.anthropic.com)
- `FIRECRAWL_API_KEY` - Get from [firecrawl.dev](https://firecrawl.dev)
- `SMTP_USER` - Your Gmail address
- `SMTP_PASSWORD` - Gmail App Password (not your regular password)
- `EMAIL_TO` - Editor's email address
- `EMAIL_CC` - CC email address

### 3. Gmail Setup

**App Password:**
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Factor Authentication
3. Go to App Passwords → Create new for "Mail"
4. Use this 16-character password as `SMTP_PASSWORD`

**Enable IMAP** (for reply listener):
1. Gmail Settings → See all settings → Forwarding and POP/IMAP
2. Enable IMAP Access

### 4. GitHub Secrets

Add these secrets to your repository (Settings → Secrets → Actions):

- `ANTHROPIC_API_KEY`
- `FIRECRAWL_API_KEY`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `EMAIL_TO`
- `EMAIL_CC`

## Usage

### Run Locally

```bash
# Full pipeline with email
python src/main.py

# Preview only (no email sent)
python src/main.py --preview

# Custom article count
python src/main.py --articles 15

# Custom date range
python src/main.py --days 14
```

### Finalize Issue Manually

```bash
# Preview final issue
python src/finalize.py "1,3,5,7,9,11" --preview

# Send final issue email
python src/finalize.py "1,3,5,7,9,11"
```

### Run Listener Manually

```bash
python -m src.listener
```

### GitHub Actions

**Weekly Digest** (Fridays 6AM CST):
- Runs automatically on schedule
- Manual: Actions → Weekly Newsletter Digest → Run workflow

**Reply Listener** (Every 15 min Fri/Sat):
- Runs automatically on schedule
- Manual: Actions → Reply Listener → Run workflow

## Project Structure

```
pulse-newsletter/
├── .github/workflows/
│   ├── weekly-digest.yml    # Friday menu generation
│   └── listener.yml         # Reply monitoring
├── src/
│   ├── main.py              # Pipeline orchestrator
│   ├── feeds.py             # RSS fetching + URL resolution
│   ├── deduper.py           # Deduplication
│   ├── categorizer.py       # Classification + source filtering
│   ├── scraper.py           # Firecrawl integration
│   ├── summarizer.py        # Claude summaries
│   ├── emailer.py           # Gmail SMTP
│   ├── finalize.py          # Final issue generation
│   └── listener.py          # Email reply monitoring
├── config/
│   ├── categories.py        # Category definitions
│   └── queries.py           # Search queries
├── data/
│   └── latest_summaries.json  # Saved for listener
├── requirements.txt
├── .env.example
└── README.md
```

## Output Formats

### Menu Email (for review)

```markdown
**1.** 🧠 **[Headline Here](https://source-url.com)**
Summary in 3 sentences. First sets up the situation. Second adds
key details. Third implies significance.
*Source: Publication Name*
```

### Final Issue (Beehiiv-ready)

```markdown
THIS WEEK AT A GLANCE

• Short punchy theme (12-15 words max)
• Another key takeaway
• Third theme

———

1️⃣ AI & EDTECH

🧠 [Headline Here](https://source-url.com)

Summary paragraph in 3 sentences...

———
```

## Customization

### Modify Search Queries
Edit `config/queries.py` to adjust search keywords and topic areas.

### Modify Categories
Edit `config/categories.py` to add/remove categories or adjust keywords.

### Block Sources
Edit `BLOCKED_SOURCES` in `src/categorizer.py` to filter out unwanted publications.

### Modify Voice/Tone
Edit the `SYSTEM_PROMPT` in `src/summarizer.py` to adjust Claude's writing style.

## Troubleshooting

### Empty summaries
- Usually means URL resolution failed and Firecrawl couldn't scrape
- The backfill system will try backup articles automatically

### Blocked sources appearing
- Add the source name to `BLOCKED_SOURCES` in `src/categorizer.py`
- Source filtering works even when URL resolution fails

### Listener not finding replies
- Ensure reply is from `EMAIL_TO` address
- Ensure reply is marked as UNREAD
- Subject must contain "Re:" and "PulseK12"

### Email not sending
- Verify Gmail app password is correct
- Ensure IMAP is enabled for listener

## Cost Estimates

Per weekly run (~20 articles):
- **Anthropic Claude**: ~$0.15-0.25
- **Firecrawl**: ~20 scrapes (check your plan)
- **GitHub Actions**: Free tier sufficient

# PulseK12 Newsletter Automation Engine

Automated weekly newsletter generation for K-12 education news.

## How It Works

Every Friday at 6:00 AM CST, this system:

1. **Fetches** ~40 articles from Google News RSS feeds across 6 topic areas
2. **Deduplicates** and filters to remove duplicates and off-topic content
3. **Classifies** articles into 8 categories and selects a balanced menu of 20
4. **Scrapes** full article content using Firecrawl
5. **Summarizes** each article using Claude 3.5 Sonnet
6. **Emails** the formatted menu for editorial review

## Categories

| Emoji | Category | Topics |
|-------|----------|--------|
| 🧠 | AI & EdTech | AI tools, education technology, innovation |
| 📜 | Policy Watch | Legislation, funding, regulations |
| 🎓 | Teaching & Learning | Instruction, curriculum, PD |
| 📊 | Research & Data | Studies, reports, findings |
| 🏫 | District Spotlight | Success stories, implementations |
| 🔒 | Safety & Privacy | School safety, data security |
| 💚 | Student Wellness | Mental health, attendance, SEL |
| 👥 | Leadership | Admin insights, staffing |

## Setup

### 1. Clone and Install

```bash
git clone <your-repo-url>
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
- `SMTP_USER` - Your Gmail address (team@pulsek12.com)
- `SMTP_PASSWORD` - Gmail App Password (not your regular password)

### 3. Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Factor Authentication if not already enabled
3. Go to App Passwords
4. Create a new app password for "Mail"
5. Use this 16-character password as `SMTP_PASSWORD`

### 4. GitHub Secrets

Add these secrets to your GitHub repository (Settings → Secrets → Actions):

- `ANTHROPIC_API_KEY`
- `FIRECRAWL_API_KEY`
- `SMTP_USER` (team@pulsek12.com)
- `SMTP_PASSWORD` (Gmail app password)
- `EMAIL_TO` (khunter8989@gmail.com)
- `EMAIL_CC` (andydue@gmail.com)

## Usage

### Run Locally

```bash
# Full pipeline with email
python src/main.py

# Preview only (no email sent)
python src/main.py --preview

# Custom date range
python src/main.py --days 14

# Skip email entirely
python src/main.py --no-email
```

### Manual GitHub Actions Run

1. Go to Actions tab in GitHub
2. Select "Weekly Newsletter Digest"
3. Click "Run workflow"
4. Optionally adjust days_back or enable preview mode

## Project Structure

```
pulse-newsletter/
├── .github/workflows/
│   └── weekly-digest.yml    # CRON trigger
├── src/
│   ├── main.py              # Orchestrator
│   ├── feeds.py             # RSS fetching
│   ├── deduper.py           # Deduplication
│   ├── categorizer.py       # Classification + balancing
│   ├── scraper.py           # Firecrawl integration
│   ├── summarizer.py        # Claude summaries
│   └── emailer.py           # Gmail SMTP
├── config/
│   ├── categories.py        # Category definitions
│   └── queries.py           # Search queries
├── templates/
│   └── menu.md              # Output template
├── requirements.txt
├── .env.example
└── README.md
```

## Customization

### Modify Search Queries

Edit `config/queries.py` to adjust:
- Search keywords for each topic
- Trusted news sources
- Query groupings

### Modify Categories

Edit `config/categories.py` to:
- Add/remove categories
- Change emoji mappings
- Adjust keyword hints for classification

### Modify Voice/Tone

Edit the `SYSTEM_PROMPT` in `src/summarizer.py` to adjust Claude's writing style.

## Output Format

Each story in the menu includes:

```markdown
### 🧠 [Compelling Headline Here](https://source-url.com)

**The Gist:** Two sentences summarizing what happened and the key takeaway.

**Why It Matters:** One sentence on why K-12 leaders should care.

*Source: Publication Name*
```

## Troubleshooting

### No articles found
- Check if Google News RSS is accessible
- Verify search queries are returning results
- Try increasing `--days` parameter

### Scraping failures
- Some sites block scrapers - these articles will use RSS summary
- Check Firecrawl API quota

### Email not sending
- Verify Gmail app password is correct
- Check if "Less secure app access" might be needed
- Review GitHub Actions logs for SMTP errors

## Cost Estimates

Per weekly run (~20 articles):
- **Anthropic Claude**: ~$0.10-0.20 (depending on article length)
- **Firecrawl**: Check your plan limits
- **GitHub Actions**: Free tier is sufficient

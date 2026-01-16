# PulseK12 Newsletter Automation Engine

Automated weekly newsletter generation for K-12 education news. Fetches articles from Google News RSS, filters/categorizes them, scrapes full content, generates summaries with Claude, and emails a menu for editorial review.

## Project Structure

```
pulse-newsletter/
├── .github/workflows/
│   ├── weekly-digest.yml    # Friday 12pm CST - generates menu
│   └── listener.yml         # Fri-Sat - monitors for replies + URL submissions
├── src/
│   ├── main.py              # Pipeline orchestrator
│   ├── feeds.py             # RSS fetching + Google News URL resolution
│   ├── deduper.py           # Title/URL deduplication
│   ├── categorizer.py       # Classification, filtering, scoring, selection
│   ├── scraper.py           # Firecrawl integration for full article content
│   ├── summarizer.py        # Claude summaries with PulseK12 voice
│   ├── emailer.py           # Gmail SMTP sending
│   ├── finalize.py          # Final issue generation from selections
│   ├── listener.py          # Email monitoring: menu replies + URL submissions
│   └── local_themes.py      # Local story theme clustering
├── config/
│   ├── categories.py        # 8 category definitions with keywords
│   └── queries.py           # Google News RSS search queries
└── data/
    └── latest_summaries.json  # Saved between digest and listener runs
```

## Pipeline Flow

1. **Fetch** ~350 articles from 6 Google News RSS queries
2. **Filter** to ~170 relevant K-12 education articles
3. **Deduplicate** by title similarity and URL
4. **Classify** into 8 categories with quality scoring
5. **Select** balanced menu (15-20 national + local themes)
6. **Scrape** full content via Firecrawl API
7. **Summarize** with Claude (3 sentences, PulseK12 voice)
8. **Email** menu for editorial review
9. **Listen** for reply with selections
10. **Generate** final Beehiiv-ready issue

## On-Demand URL Summaries

The listener also supports on-demand summarization. Email article URLs (one per line) from the authorized sender address, and receive PulseK12-styled summaries back via email reply.

**How it works:**
1. Email URLs to the system (one per line in body)
2. System detects URLs vs menu selections automatically
3. Scrapes each article via Firecrawl
4. Generates summaries with Claude using PulseK12 voice
5. Replies with formatted summaries

**Limits:**
- Max 10 URLs per request (rate limiting)
- Same schedule window as menu replies (Friday 12pm - Saturday midnight CST)

## Key Files to Understand

- `src/categorizer.py` - The brain. Handles relevance filtering, source blocking, authority scoring, local detection, category classification, and balanced selection. Most filtering logic lives here.
- `src/summarizer.py` - Contains SYSTEM_PROMPT with voice guidelines. This is where editorial tone is enforced.
- `config/categories.py` - 8 categories with keyword lists for classification
- `config/queries.py` - Google News search queries that seed the pipeline

## Environment Variables

```
ANTHROPIC_API_KEY    # Claude API
FIRECRAWL_API_KEY    # Article scraping
SMTP_USER            # Gmail address
SMTP_PASSWORD        # Gmail app password
EMAIL_TO             # Editor's email
EMAIL_CC             # CC email
```

---

# Editorial Guidelines

## Who We Are

PulseK12 is a weekly newsletter for K-12 education leaders. We sit **between research, practice, and policy** - not press releases or trend-chasing blogs.

## What We Include

### High Priority Content Types

1. **Practitioner spotlights** - Real administrators implementing real things. District leaders, tech directors, principals doing innovative work. "How [Person] is transforming [District] through [Approach]"

2. **Research with implications** - Studies that explain what findings mean for schools. The "so what" matters more than novelty. Not just "study finds X" but "X means schools should consider Y"

3. **Actionable guidance** - "How to" content for school leaders. Strategies, approaches, guidance they can use Monday morning.

4. **Structural challenges with data** - Reports showing systemic issues with numbers. "40% of programs struggle with X" - gives leaders context for their own challenges.

5. **State policy with concrete action** - Not funding debates, but specific initiatives. Task forces, new laws, program launches with clear implications.

6. **Enrollment/demographic trends** - Shifts in who attends public schools and why. These have policy and practice implications.

### Content Attributes We Value

- Credible, field-connected sources
- Clear implications for practitioners
- Specific numbers and data points
- Real voices from the field
- Open access (not paywalled)

## What We Exclude

### Hard Filters (always exclude)

- **Higher education** - Universities, colleges, professors. We are K-12 only.
- **Press releases** - Product announcements, partnership announcements without research/outcomes
- **International content** - Non-US education news
- **Hyper-local events** - Single school reading nights, local fundraisers
- **Roundup/listicle articles** - "Top 10 stories of the week" (meta-content)
- **Vendor-sponsored content** - Advocacy disguised as reporting

### Soft Filters (deprioritize)

- **Pure funding stories** - Unless they discuss student outcome implications
- **Gated/paywalled content** - We promote open sources readers can access
- **Trend-chasing blogs** - Hot takes without substance
- **Product features** - Unless validated with research or outcomes

## Blocked Sources

### Domains
- Press release mills: prweb.com, prnewswire.com, businesswire.com
- International: .uk, .ca, .au domains, bbc.com, theguardian.com
- Off-topic: bollywood, cricket, sports, celebrity
- Hyper-local: hometownstations.com, sj-r.com
- Low quality: usaherald.com, gritdaily.com, demandsage.com

### Source Names
- PR Newswire, Business Wire, PRWeb
- Non-US regional outlets
- Press release aggregators

## Trusted Sources (Authority Tiers)

### Tier 1 (Premier K-12 outlets) - +0.3 score
- k12dive.com
- the74million.org
- chalkbeat.org
- edweek.org / educationweek.org
- hechingerreport.org

### Tier 2 (Respected education media) - +0.2 score
- edsurge.com
- edutopia.org
- edsource.org
- eschoolnews.com
- techlearning.com
- districtadministration.com

### Tier 3 (Research/policy organizations) - +0.1 score
- brookings.edu
- rand.org
- nwea.org
- iste.org

## Voice & Tone (for summaries)

- Write like a smart insider briefing a colleague
- Assume the reader knows the education space
- Lead sentences with the actor/subject: "District leaders...", "Rural students..."
- Use specific numbers: "more than 15 percentage points", "over half"
- Never start with "However," "Additionally," "Furthermore," "Moreover"
- No filler phrases. No hedging. Direct and declarative.
- Weave significance in naturally - don't preach about why it matters
- End with implication, not instruction
- No exclamation points. Professional warmth, not enthusiasm.

## Categories

| Emoji | Category | Focus |
|-------|----------|-------|
| 🧠 | AI & EdTech | AI tools, education technology, innovation |
| 📜 | Policy Watch | Legislation, funding with outcomes, regulations |
| 🎓 | Teaching & Learning | Instruction, curriculum, literacy, PD |
| 📊 | Research & Data | Studies with implications, reports, findings |
| 🏫 | District Spotlight | Success stories, implementations |
| 🔒 | Safety & Privacy | School safety, data security |
| 💚 | Student Wellness | Mental health, attendance, SEL |
| 👥 | Leadership | Admin insights, staffing, district leaders |

---

# Development Notes

## Running Locally

```bash
# Full pipeline with email
python src/main.py

# Preview only (no email)
python src/main.py --preview

# Custom article count
python src/main.py --articles 20

# Run listener manually
python -m src.listener

# Finalize with specific selections
python src/finalize.py "1,3,5,7,9" --preview
```

## Common Issues

- **Empty summaries**: Usually URL resolution failed. Backfill system tries backup articles.
- **Blocked sources appearing**: Add to BLOCKED_SOURCES or BLOCKED_DOMAINS in categorizer.py
- **Listener not finding menu replies**: Check reply is from EMAIL_TO, marked UNREAD, subject contains "Re:" and "PulseK12"
- **URL submissions not detected**: Ensure URLs are one per line, email is from EMAIL_TO, and is marked UNREAD
- **Scraping failures**: Firecrawl rate limit is 10 req/min. SCRAPE_DELAY_SECONDS controls pacing.

## Cost Per Run

- Anthropic Claude: ~$0.15-0.25 (20 articles)
- Firecrawl: ~20 scrapes
- GitHub Actions: Free tier

## Schedule (UTC)

- Weekly Digest: Friday 18:00 UTC (12pm CST)
- Listener: Friday 18:00 UTC through Sunday 06:00 UTC (36 hour window)

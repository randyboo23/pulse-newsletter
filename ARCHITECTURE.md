# PulseK12 Newsletter Architecture

## Overview

Automated weekly newsletter pipeline for K-12 education news. Fetches articles from Google News RSS, filters/scores them, generates summaries with Claude, and produces Beehiiv-ready output.

## Pipeline Flow

```
RSS Feeds (6 topics)
    ↓
Date Filter → Deduplication → Relevance Filter
    ↓
Classification + Quality Scoring
    ↓
┌─────────────────┬─────────────────┐
│  National Pool  │   Local Pool    │
│   (232+ articles)│   (10-20 articles)│
└────────┬────────┴────────┬────────┘
         ↓                  ↓
   Firecrawl Scrape    Theme Clustering
         ↓                  ↓
   Claude Summaries    Local Spotlight
         ↓                  ↓
└─────────────────┴─────────────────┘
                ↓
         Email Menu → Editor Reply → Final Issue
```

## Schedule

- **Friday 12pm CST**: Weekly digest runs (menu generation)
- **Friday 12pm - Saturday midnight CST**: Reply listener monitors for editor selections + URL submissions (36-hour window)

## Module Responsibilities

### src/main.py
Pipeline orchestrator. Coordinates all stages and saves output to `data/latest_summaries.json`.

### src/feeds.py
- Fetches 6 Google News RSS feeds (AI/EdTech, Policy, Teaching, Safety, Wellness, General)
- Resolves Google News redirect URLs to actual article URLs
- Uses `googlenewsdecoder` with HTTP fallback

### src/deduper.py
- Removes duplicate articles by title similarity
- Counts feed appearances for trending detection

### src/categorizer.py
Core filtering and scoring logic:

**Filters (is_relevant_article)**
- `is_blocked_source()` - blocked domains/sources
- `is_roundup_article()` - listicles, weekly roundups
- `is_higher_ed_article()` - university/college content (K-12 only)
- `is_press_release_url()` - /press-release/ URL patterns
- `is_international_story()` - non-US content

**Quality Scoring (calculate_quality_score)**
- `category_score`: 0-1.0 (keyword matching)
- `authority_score`: 0-0.3 (source tier)
- `trending_score`: 0-0.3 (multi-feed appearances)
- `content_type_boost`: -0.4 to +0.5 (editorial priorities)
- `local_penalty`: -0.2 (if local story)

**Content Type Boosts**
| Type | Boost | Keywords |
|------|-------|----------|
| Practitioner spotlight | +0.15 | director, implementing, transformation |
| Actionable guidance | +0.15 | how to, strategies, tips |
| Research implications | +0.1 | implications for, schools should |
| Data challenges | +0.1 | report finds, percent of |
| Enrollment trends | +0.1 | enrollment, demographic |
| State policy action | +0.1 | task force, initiative (with state name) |

**Content Type Penalties**
| Type | Penalty | Keywords |
|------|---------|----------|
| Vendor-sponsored | -0.2 | sponsored content, paid content |
| Hyper-local events | -0.2 | reading night, pta meeting |
| Funding-only | -0.15 | budget proposal (without outcomes) |
| Product announcements | -0.15 | launches new, now available |

**Source Tiers**
- Tier 1 (+0.3): k12dive, the74million, chalkbeat, edweek, hechingerreport
- Tier 2 (+0.2): edsurge, edutopia, edsource, eschoolnews, techlearning
- Tier 3 (+0.1): brookings, rand, nwea, iste

### src/scraper.py
- Firecrawl API integration for full article content
- Rate limited to ~8 requests/minute
- Fallback content extraction from RSS summary

### src/summarizer.py
Claude-powered article summarization:
- Model: claude-sonnet-4-20250514
- Output: Headline (5-10 words) + Summary (3 sentences)
- Editorial philosophy embedded in system prompt

### src/local_themes.py
Clusters local stories by theme using Claude:
- Groups 2-4 related stories per theme
- Generates synthesized blurbs with state references
- **US-only filter**: Validates states against US_STATES set
- Returns up to 2 themes for Local Spotlight section

### src/emailer.py
Gmail SMTP integration for sending menu and final issues.

### src/finalize.py
Generates final newsletter from editor selections:
- Loads national summaries + local themes
- Generates "This Week at a Glance" bullets
- Formats Beehiiv-ready markdown
- Includes Local Spotlight section automatically

### src/listener.py
Monitors Gmail for editor replies with selections and/or URLs:
- Parses article numbers from reply (strips URLs first to avoid false matches)
- Extracts submitted URLs for on-demand summarization
- Combines menu selections + URL summaries in single response
- Filters international sources (US-only)
- Runs every 15 minutes during listener window

## Data Structures

### data/latest_summaries.json
```json
{
  "generated_at": "2026-01-10T06:00:00",
  "count": 20,
  "summaries": [...],           // National article summaries
  "local_themes": [...],        // Themed local story clusters
  "local_articles": [...],      // Original local articles
  "local_theme_count": 2
}
```

### Article Object
```json
{
  "title": "...",
  "url": "...",
  "resolved_url": "...",
  "source": "...",
  "category": "ai_edtech",
  "category_score": 0.67,
  "authority_score": 0.3,
  "trending_score": 0.1,
  "content_type_boost": 0.15,
  "content_boost_reason": "practitioner_spotlight",
  "local_penalty": 0.0,
  "is_local": false,
  "total_score": 1.22,
  "full_content": "..."
}
```

### Local Theme Object
```json
{
  "theme_title": "School Choice Momentum",
  "blurb": "Texas, Florida, and Ohio each advanced...",
  "article_indices": [0, 3, 7],
  "states_mentioned": ["Texas", "Florida", "Ohio"]
}
```

## Categories

| ID | Name | Emoji |
|----|------|-------|
| ai_edtech | AI & EdTech | 🧠 |
| policy | Policy Watch | 📜 |
| teaching | Teaching & Learning | 🎓 |
| safety | Safety & Privacy | 🔒 |
| wellness | Student Wellness | 💚 |
| research | Research & Data | 📊 |
| district | District Spotlight | 🏫 |
| workforce | Educator Workforce | 👩‍🏫 |

## GitHub Actions

### weekly-digest.yml
- Cron: `0 18 * * 5` (Friday 12pm CST / 18:00 UTC)
- Runs full pipeline, sends menu email
- Commits updated summaries to repo

### listener.yml
- Crons: `*/15 18-23 * * 5` + `*/15 0-23 * * 6` + `*/15 0-5 * * 0`
- 36-hour window: Friday 12pm CST - Saturday midnight CST
- Handles both menu replies and URL submissions
- Scrapes/summarizes submitted URLs with Firecrawl + Claude

## Environment Variables

```
ANTHROPIC_API_KEY     # Claude API
FIRECRAWL_API_KEY     # Web scraping
GMAIL_ADDRESS         # Sender email
GMAIL_APP_PASSWORD    # Gmail app password
EMAIL_TO              # Editor email
EMAIL_CC              # CC recipient (optional)
```

## Output Formats

### Menu Email
```markdown
**NATIONAL STORIES**

**1.** 🧠 **[Headline](url)**
Summary text...
*Source: Publication*

---

**LOCAL SPOTLIGHT**

**Theme Title** (State1, State2)
Synthesized blurb...
```

### Final Issue (Beehiiv)
```markdown
THIS WEEK AT A GLANCE

• Bullet point 1
• Bullet point 2

———

1️⃣ CATEGORY NAME

🧠 [Headline](url)

Summary text...

———

📍 LOCAL SPOTLIGHT

**Theme Title** (State1, State2)

Synthesized blurb...
```

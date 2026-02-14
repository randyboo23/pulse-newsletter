# PulseK12 Newsletter Architecture

## Overview

Automated weekly newsletter pipeline for K-12 education news. Fetches articles from Google News RSS, filters/scores them, generates summaries with Claude, and produces Beehiiv-ready output. Ranking is adaptive and learns from weekly editor selections and submitted URLs.

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
│  (170+ articles) │  (10-50 articles)│
└────────┬────────┴────────┬────────┘
         ↓                  ↓
   Firecrawl Scrape    50-State Topic Tracker
         ↓                  ↓
   Claude Summaries    Synthesis Article
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
Pipeline orchestrator. Coordinates all stages, loads editor feedback profile for adaptive ranking, and saves output to `data/latest_summaries.json`.

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
- `authority_score`: 0-0.6 (source tier)
- `trending_score`: 0-0.3 (multi-feed appearances)
- `content_type_boost`: -0.4 to +0.5 (editorial priorities)
- `local_penalty`: -0.2 (if local story)
- `feedback_boost`: 0-0.30 (domain/category/keyword preference signal)

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
- Tier 1 (+0.6): k12dive, the74million, chalkbeat, edweek, hechingerreport
- Tier 2 (+0.45): edsurge, edutopia, edsource, eschoolnews, techlearning
- Tier 3 (+0.25): brookings, rand, nwea, iste

### src/feedback.py
Editor feedback capture + adaptive scoring profile:
- Persists signals in `data/editor_feedback.json`
- Signal weights: menu selection (`1.0`) and submitted URL (`3.0`)
- Applies recency decay (42-day half-life, 180-day history window)
- Learns domain, category, and headline/summary token preferences

### src/scraper.py
- Firecrawl API integration for full article content
- Rate limited to ~8 requests/minute
- Fallback content extraction from RSS summary

### src/summarizer.py
Claude-powered article summarization:
- Model: claude-sonnet-4-20250514
- Output: Headline (5-10 words) + Summary (3 sentences)
- Editorial philosophy embedded in system prompt

### src/state_tracker/ (50-State Topic Tracker)
Tracks one trending K-12 topic across states and generates a synthesis article.

**Pipeline:**
1. **Topic Selection** (`topic_selection.py`) - Score: `state_count × article_count`
2. **Source Tiering** (`source_tiering.py`) - Classify A/B/C, filter Tier C
3. **Deduplication** (`deduplication.py`) - Title similarity + semantic clustering
4. **Theme Extraction** (`theme_extraction.py`) - Metadata tagging, national themes
5. **Synthesis** (`synthesis.py`) - Structured ~600 word article
6. **Guardrails** (`guardrails.py`) - Citation verification, flagging

**Priority Topics (guidelines):**
- Attendance & Engagement
- Instructional Time & Scheduling
- AI Guardrails & Pilots
- Assessment Redesign
- Staffing Model Shifts

**Source Tiers:**
- Tier A: `.gov`, state DOE, named-reporter local journalism
- Tier B: Regional outlets, policy orgs, local TV citing documents
- Tier C (blocked): Content farms, SEO rewrites, press release mills

**Output Structure:**
- What's happening (2-3 sentences)
- What's driving it (context)
- What states are doing (themes + 6-10 state snapshots)
- What districts can do this week (3-5 actions)
- What to watch next
- Sources (primary first)

**Guardrail Flags:**
- `[REPORTED]` - Policy claim without Tier A verification
- `[VERIFY: reason]` - Uncertain state inference

### src/local_themes.py (DEPRECATED)
Legacy local story clustering. Replaced by state_tracker/ package.
Kept for backward compatibility with older data files.

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
- Extracts submitted URLs for on-demand summarization (up to 20 per request)
- Combines menu selections + URL summaries in single response
- Filters international sources (US-only)
- Logs selections + submitted URLs as feedback events for future ranking
- Runs every 15 minutes during listener window

## Data Structures

### data/latest_summaries.json
```json
{
  "generated_at": "2026-01-10T06:00:00",
  "count": 20,
  "summaries": [...],           // National article summaries
  "state_tracker": {            // 50-State Topic Tracker result
    "topic": "attendance_engagement",
    "topic_label": "Attendance & Engagement",
    "synthesis": {...},         // Article sections
    "articles_used": 12,
    "states_covered": ["Texas", "California", ...],
    "themes": [...],
    "sources": [...],
    "verification": {...}
  },
  "local_themes": [],           // Legacy (empty for backward compat)
  "local_articles": [...]       // Original local articles
}
```

### data/editor_feedback.json
```json
{
  "version": 1,
  "updated_at": "2026-02-14T19:30:00+00:00",
  "events": [
    {
      "timestamp": "2026-02-14T19:30:00+00:00",
      "signal": "submitted_url",
      "weight": 3.0,
      "domain": "chalkbeat.org",
      "category": null,
      "tokens": ["attendance", "absenteeism", "intervention"]
    }
  ]
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
  "feedback_boost": 0.07,
  "feedback_reason": "domain:chalkbeat.org,tokens:attendance,absenteeism",
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
- Scrapes/summarizes submitted URLs with Firecrawl + Claude (max 20 URLs per email)

## Environment Variables

```
ANTHROPIC_API_KEY     # Claude API
FIRECRAWL_API_KEY     # Web scraping
SMTP_HOST             # SMTP host (default smtp.gmail.com)
SMTP_PORT             # SMTP port (default 587)
SMTP_USER             # Sender email / Gmail user
SMTP_PASSWORD         # Gmail app password
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

**50-STATE TOPIC TRACKER**

## Attendance & Engagement: This Week Across States

**What's Happening**
Activity on attendance continues across 8 states...

**What States Are Doing**
- Theme bullets
**Texas**: Specific action (Source)
**California**: Specific action (Source)

**Sources**
- [Primary] [Source](url)
- [Source](url)
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

📍 50-STATE TOPIC TRACKER

**Attendance & Engagement: This Week Across States**

**What's Happening**
Activity on attendance continues...

**What's Driving It**
Post-pandemic pressures...

**What States Are Doing**
- Theme bullets
**Texas**: Specific action (Source)
**California**: Specific action (Source)

**What Districts Can Do This Week**
- Action item 1
- Action item 2

**What to Watch Next**
- Upcoming deadlines...

**Sources**
- 📌 [Primary Source](url)
- [Source](url)
```

"""
Category definitions for PulseK12 newsletter.
8 categories with emoji mappings and keyword hints for classification.
"""

CATEGORIES = {
    "ai_edtech": {
        "name": "AI & EdTech",
        "emoji": "🧠",
        "keywords": [
            "artificial intelligence", "AI", "edtech", "education technology",
            "machine learning", "chatbot", "adaptive learning", "personalized learning",
            "digital tools", "future-ready", "innovation"
        ]
    },
    "policy": {
        "name": "Policy Watch",
        "emoji": "📜",
        "keywords": [
            "legislation", "policy", "law", "regulation", "funding", "budget",
            "federal", "state", "mandate", "compliance", "title I", "ESSER",
            "governor", "congress", "department of education"
        ]
    },
    "teaching": {
        "name": "Teaching & Learning",
        "emoji": "🎓",
        "keywords": [
            "instruction", "curriculum", "pedagogy", "classroom", "teaching",
            "learning", "professional development", "PD", "lesson", "assessment",
            "literacy", "math instruction", "reading", "student engagement"
        ]
    },
    "research": {
        "name": "Research & Data",
        "emoji": "📊",
        "keywords": [
            "study", "research", "report", "data", "findings", "survey",
            "analysis", "statistics", "evidence", "outcomes", "results",
            "NAEP", "test scores", "achievement gap"
        ]
    },
    "district": {
        "name": "District Spotlight",
        "emoji": "🏫",
        "keywords": [
            "district", "superintendent", "school board", "success story",
            "implementation", "initiative", "program", "pilot", "rollout",
            "case study", "best practice"
        ]
    },
    "safety": {
        "name": "Safety & Privacy",
        "emoji": "🔒",
        "keywords": [
            "safety", "security", "privacy", "data protection", "cybersecurity",
            "threat", "emergency", "behavior", "discipline", "SRO",
            "student data", "FERPA", "COPPA"
        ]
    },
    "wellness": {
        "name": "Student Wellness",
        "emoji": "💚",
        "keywords": [
            "mental health", "wellness", "SEL", "social emotional",
            "absenteeism", "attendance", "chronic absence", "MTSS",
            "counseling", "trauma", "anxiety", "support services"
        ]
    },
    "leadership": {
        "name": "Leadership",
        "emoji": "👥",
        "keywords": [
            "leadership", "principal", "administrator", "management",
            "strategic", "vision", "culture", "staff", "hiring",
            "retention", "teacher shortage", "burnout"
        ]
    }
}

# Target distribution for balanced menu (min, max per category)
CATEGORY_BALANCE = {
    "min_per_category": 2,
    "max_per_category": 5,
    "total_target": 25
}


def get_category_by_id(category_id: str) -> dict:
    """Get category details by ID."""
    return CATEGORIES.get(category_id, {})


def get_all_categories() -> list[str]:
    """Get list of all category IDs."""
    return list(CATEGORIES.keys())


def format_category_label(category_id: str) -> str:
    """Format category as 'emoji Name' for display."""
    cat = CATEGORIES.get(category_id, {})
    return f"{cat.get('emoji', '📰')} {cat.get('name', 'General')}"

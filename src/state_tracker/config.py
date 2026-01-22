"""
Configuration for 50-State Topic Tracker.

Contains:
- Priority topic definitions with keywords
- Source tier definitions (A/B/C)
- Domain mappings for state detection
- Thresholds and constants
"""

# Minimum requirements for synthesis
MIN_STATES_FOR_SYNTHESIS = 3
MIN_ARTICLES_FOR_SYNTHESIS = 3
TARGET_WORD_COUNT = 600

# Priority topics with keyword sets
# These are guidelines - the system can also detect emergent topics
PRIORITY_TOPICS = {
    "attendance_engagement": {
        "label": "Attendance & Engagement",
        "keywords": [
            "chronic absenteeism", "absenteeism", "attendance",
            "truancy", "truant", "engagement", "early warning",
            "dropout", "drop out", "re-engagement", "reengagement",
            "missing school", "absent", "attendance rate",
            "compulsory attendance", "school attendance"
        ]
    },
    "instructional_time": {
        "label": "Instructional Time & Scheduling",
        "keywords": [
            "four-day week", "4-day week", "four day week",
            "extended day", "extended learning", "instructional time",
            "school calendar", "bell schedule", "summer learning",
            "year-round school", "school hours", "instructional minutes",
            "learning time", "seat time", "class schedule"
        ]
    },
    "ai_guardrails": {
        "label": "AI Guardrails & Pilots",
        "keywords": [
            "ai policy", "ai guardrails", "ai guardrail",
            "chatgpt policy", "chatgpt", "generative ai",
            "ai acceptable use", "ai use policy", "artificial intelligence policy",
            "ai pilot", "ai in schools", "ai ban", "ai guidelines",
            "machine learning", "ai tutoring", "ai cheating"
        ]
    },
    "assessment_redesign": {
        "label": "Assessment Redesign",
        "keywords": [
            "assessment reform", "testing reform", "competency-based",
            "competency based", "standardized testing", "naep",
            "assessment redesign", "test score", "state assessment",
            "high-stakes testing", "testing opt-out", "performance assessment",
            "formative assessment", "benchmark assessment", "interim assessment"
        ]
    },
    "staffing_models": {
        "label": "Staffing Model Shifts",
        "keywords": [
            "teacher shortage", "staffing model", "substitute crisis",
            "teacher residency", "grow your own", "para-professional",
            "paraprofessional", "teacher pipeline", "alternative certification",
            "teacher vacancy", "teacher vacancies", "staffing shortage",
            "hiring freeze", "teacher retention", "staff turnover"
        ]
    },
    "school_funding": {
        "label": "School Funding & Budgets",
        "keywords": [
            "school funding", "funding formula", "education budget",
            "per-pupil", "per pupil", "state aid", "budget proposal",
            "school budget", "education funding", "funding gap",
            "property tax", "school finance", "budget shortfall",
            "funding increase", "funding cut", "adequacy", "budget chairman",
            "education appropriations", "school tax"
        ]
    },
    "literacy_reading": {
        "label": "Literacy & Reading",
        "keywords": [
            "literacy", "reading", "science of reading", "phonics",
            "literacy coach", "reading specialist", "reading intervention",
            "early literacy", "literacy grant", "reading program",
            "dyslexia", "literacy initiative", "reading proficiency",
            "third-grade reading", "literacy rate", "reading scores"
        ]
    }
}

# Domain to state mapping for common local news outlets
DOMAIN_STATE_MAP = {
    # Texas
    "texastribune.org": "Texas",
    "dallasnews.com": "Texas",
    "houstonchronicle.com": "Texas",
    "chron.com": "Texas",
    "statesman.com": "Texas",
    "expressnews.com": "Texas",
    "star-telegram.com": "Texas",
    # California
    "latimes.com": "California",
    "sfchronicle.com": "California",
    "sfgate.com": "California",
    "sacbee.com": "California",
    "sandiegouniontribune.com": "California",
    "ocregister.com": "California",
    "mercurynews.com": "California",
    "edsource.org": "California",
    # Florida
    "tampabay.com": "Florida",
    "sun-sentinel.com": "Florida",
    "miamiherald.com": "Florida",
    "orlandosentinel.com": "Florida",
    "jacksonville.com": "Florida",
    # New York
    "nydailynews.com": "New York",
    "newsday.com": "New York",
    "lohud.com": "New York",
    "democratandchronicle.com": "New York",
    "buffalonews.com": "New York",
    # Pennsylvania
    "inquirer.com": "Pennsylvania",
    "post-gazette.com": "Pennsylvania",
    "pennlive.com": "Pennsylvania",
    # Illinois
    "chicagotribune.com": "Illinois",
    "suntimes.com": "Illinois",
    # Ohio
    "cleveland.com": "Ohio",
    "dispatch.com": "Ohio",
    "cincinnati.com": "Ohio",
    # Michigan
    "freep.com": "Michigan",
    "detroitnews.com": "Michigan",
    "mlive.com": "Michigan",
    # Georgia
    "ajc.com": "Georgia",
    # North Carolina
    "charlotteobserver.com": "North Carolina",
    "newsobserver.com": "North Carolina",
    "ednc.org": "North Carolina",
    # Arizona
    "azcentral.com": "Arizona",
    "tucson.com": "Arizona",
    # Colorado
    "denverpost.com": "Colorado",
    "coloradosun.com": "Colorado",
    # Washington
    "seattletimes.com": "Washington",
    # Massachusetts
    "bostonglobe.com": "Massachusetts",
    "boston.com": "Massachusetts",
    # Minnesota
    "startribune.com": "Minnesota",
    # Wisconsin
    "jsonline.com": "Wisconsin",
    # Indiana
    "indystar.com": "Indiana",
    # Missouri
    "stltoday.com": "Missouri",
    "kansascity.com": "Missouri",
    # Tennessee
    "tennessean.com": "Tennessee",
    # Maryland
    "baltimoresun.com": "Maryland",
    # Virginia
    "virginiamercury.com": "Virginia",
    "dailypress.com": "Virginia",
    # Oregon
    "oregonlive.com": "Oregon",
    # Nevada
    "reviewjournal.com": "Nevada",
    # Iowa
    "desmoinesregister.com": "Iowa",
    # Kentucky
    "courier-journal.com": "Kentucky",
    # Louisiana
    "nola.com": "Louisiana",
    "theadvocate.com": "Louisiana",
    # Alabama
    "al.com": "Alabama",
    # Oklahoma
    "oklahoman.com": "Oklahoma",
    # South Carolina
    "thestate.com": "South Carolina",
    "postandcourier.com": "South Carolina",
    # Connecticut
    "ctpost.com": "Connecticut",
    "courant.com": "Connecticut",
    # Utah
    "sltrib.com": "Utah",
    "deseret.com": "Utah",
    # Arkansas
    "arkansasonline.com": "Arkansas",
    # Kansas
    "kansas.com": "Kansas",
    # Mississippi
    "clarionledger.com": "Mississippi",
    # New Mexico
    "abqjournal.com": "New Mexico",
    # Nebraska
    "omaha.com": "Nebraska",
    # West Virginia
    "wvgazettemail.com": "West Virginia",
    # Hawaii
    "staradvertiser.com": "Hawaii",
    # Idaho
    "idahostatesman.com": "Idaho",
    # Maine
    "pressherald.com": "Maine",
    # New Hampshire
    "unionleader.com": "New Hampshire",
    # Rhode Island
    "providencejournal.com": "Rhode Island",
    # Montana
    "billingsgazette.com": "Montana",
    # Delaware
    "delawareonline.com": "Delaware",
    # South Dakota
    "argusleader.com": "South Dakota",
    # North Dakota
    "inforum.com": "North Dakota",
    # Alaska
    "adn.com": "Alaska",
    # Vermont
    "burlingtonfreepress.com": "Vermont",
    # Wyoming
    "trib.com": "Wyoming",
}

# State DOE domain patterns (partial matches)
STATE_DOE_PATTERNS = {
    "tea.texas.gov": "Texas",
    "cde.ca.gov": "California",
    "fldoe.org": "Florida",
    "nysed.gov": "New York",
    "education.pa.gov": "Pennsylvania",
    "isbe.net": "Illinois",
    "education.ohio.gov": "Ohio",
    "michigan.gov/mde": "Michigan",
    "gadoe.org": "Georgia",
    "dpi.nc.gov": "North Carolina",
    "azed.gov": "Arizona",
    "cde.state.co.us": "Colorado",
    "k12.wa.us": "Washington",
    "doe.mass.edu": "Massachusetts",
    "education.mn.gov": "Minnesota",
    "dpi.wi.gov": "Wisconsin",
    "doe.in.gov": "Indiana",
    "dese.mo.gov": "Missouri",
    "tn.gov/education": "Tennessee",
    "marylandpublicschools.org": "Maryland",
    "doe.virginia.gov": "Virginia",
    "oregon.gov/ode": "Oregon",
    "doe.nv.gov": "Nevada",
    "educateiowa.gov": "Iowa",
    "education.ky.gov": "Kentucky",
    "louisianabelieves.com": "Louisiana",
    "alsde.edu": "Alabama",
    "sde.ok.gov": "Oklahoma",
    "ed.sc.gov": "South Carolina",
    "portal.ct.gov/sde": "Connecticut",
    "schools.utah.gov": "Utah",
    "dese.ade.arkansas.gov": "Arkansas",
    "ksde.org": "Kansas",
    "mdek12.org": "Mississippi",
    "webnew.ped.state.nm.us": "New Mexico",
    "education.ne.gov": "Nebraska",
    "wvde.us": "West Virginia",
    "hawaiipublicschools.org": "Hawaii",
    "sde.idaho.gov": "Idaho",
    "maine.gov/doe": "Maine",
    "education.nh.gov": "New Hampshire",
    "ride.ri.gov": "Rhode Island",
    "opi.mt.gov": "Montana",
    "doe.k12.de.us": "Delaware",
    "doe.sd.gov": "South Dakota",
    "nd.gov/dpi": "North Dakota",
    "education.alaska.gov": "Alaska",
    "education.vermont.gov": "Vermont",
    "edu.wyoming.gov": "Wyoming",
}

# Source tier definitions
SOURCE_TIERS = {
    "tier_a": {
        # Government patterns (regex-like matches)
        "gov_patterns": [
            ".gov",
            "legislature.",
            "legis.",
            "senate.",
            "assembly.",
            "house.",
        ],
        # Named reporter local outlets (best local journalism)
        "local_journalism": [
            "texastribune.org",
            "denverpost.com",
            "startribune.com",
            "seattletimes.com",
            "bostonglobe.com",
            "latimes.com",
            "sfchronicle.com",
            "inquirer.com",
            "chicagotribune.com",
            "miamiherald.com",
            "tampabay.com",
            "ajc.com",
            "dispatch.com",
            "cleveland.com",
            "freep.com",
            "oregonlive.com",
            "baltimoresun.com",
            "virginiamercury.com",
            "coloradosun.com",
            "post-gazette.com",
        ],
        # State education news
        "state_education": [
            "edsource.org",  # California
            "ednc.org",  # North Carolina
        ]
    },
    "tier_b": {
        # Regional/policy outlets
        "domains": [
            "chalkbeat.org",
            "the74million.org",
            "k12dive.com",
            "edweek.org",
            "educationweek.org",
            "edsurge.com",
            "hechingerreport.org",
            "edutopia.org",
            "eschoolnews.com",
            "districtadministration.com",
            "brookings.edu",
            "rand.org",
        ],
        # Local TV with education reporting
        "local_tv_patterns": [
            "khou", "kxan", "wfaa", "wcnc", "wpxi",
            "wsoc", "wxia", "wkyc", "kmov", "ksdk"
        ]
    },
    "tier_c_blocked": {
        # Content farms and aggregators
        "domains": [
            "patch.com",
            "examiner.com",
            "msn.com",
            "yahoo.com",
            "aol.com",
            "newsbreak.com",
            "prweb.com",
            "prnewswire.com",
            "businesswire.com",
            "globenewswire.com",
        ],
        # Patterns to avoid
        "patterns": [
            "press-release",
            "press_release",
            "/sponsored/",
            "/partner-content/",
        ]
    }
}

# Metadata tagging categories
POLICY_TYPES = [
    "reporting_requirement",
    "intervention_mandate",
    "funding",
    "accountability",
    "family_engagement",
    "legal_enforcement",
    "staffing",
    "none"
]

STRATEGY_TYPES = [
    "incentives",
    "mentoring",
    "home_visits",
    "data_early_warning",
    "transportation",
    "health_supports",
    "community_partnerships",
    "professional_development",
    "technology",
    "other"
]

GRADE_BANDS = [
    "elementary",
    "middle",
    "high",
    "all_k12",
    "unspecified"
]

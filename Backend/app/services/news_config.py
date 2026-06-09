MAX_ARTICLES = 10
TOP_N = 3
TODAY_REFRESH_HOURS = 6
NEAREST_DAY_WINDOW = 3          # ± days to search when a date itself has no news
GDELT_MIN_INTERVAL_SEC = 5.0    # space live GDELT calls — its free API allows ~1 req / 5s

# Map our language names to ISO codes used by keyword news APIs (GNews, etc.).
LANG_CODES = {"english": "en", "french": "fr"}

# Maps a currency pair to GDELT query inputs.
PAIR_QUERIES = {
    ("EUR", "USD"): {
        "keywords": ["euro dollar", "ECB", "Federal Reserve", "eurozone economy"],
        "countries": ["US", "EU"],
        "languages": ["english"],
    },
    ("GBP", "USD"): {
        "keywords": ["pound dollar", "sterling", "Bank of England"],
        "countries": ["US", "UK"],
        "languages": ["english"],
    },
    ("USD", "TND"): {
        "keywords": ["Tunisian dinar", "Tunisia economy", "Banque Centrale de Tunisie"],
        "countries": ["TN", "US"],
        "languages": ["english", "french"],
    },
    ("EUR", "TND"): {
        "keywords": ["Tunisian dinar euro", "Tunisia trade", "BCT Tunisia"],
        "countries": ["TN", "EU"],
        "languages": ["english", "french"],
    },
}

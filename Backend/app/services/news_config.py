MAX_ARTICLES = 10
TOP_N = 3
TODAY_REFRESH_HOURS = 6

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

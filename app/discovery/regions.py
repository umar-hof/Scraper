"""Small bounded regions used for polite, resumable discovery."""

# Approximate city boxes, expressed as (south, west, north, east).
ARIZONA_REGIONS = {
    "Phoenix": (33.28, -112.25, 33.78, -111.85),
    "Scottsdale": (33.45, -112.05, 33.80, -111.75),
    "Tempe": (33.34, -111.98, 33.50, -111.85),
    "Mesa": (33.30, -111.90, 33.55, -111.55),
    "Chandler": (33.20, -112.00, 33.45, -111.65),
    "Tucson": (32.00, -111.10, 32.45, -110.65),
    "Flagstaff": (35.05, -111.80, 35.35, -111.45),
    "Yuma": (32.60, -114.80, 32.90, -114.45),
    "Prescott": (34.35, -112.65, 34.75, -112.25),
    "Glendale": (33.45, -112.35, 33.70, -112.05),
}

ICP_CATEGORIES = ("cosmetics", "candle", "coffee", "tea", "bakery", "gift", "soap", "beauty", "food")

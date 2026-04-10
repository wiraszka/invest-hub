from typing import Dict, List

COMMODITIES: Dict[str, str] = {
    "Gold": "gold",
    "Silver": "silver",
    "Platinum": "platinum",
    "Copper": "copper",
    "Uranium": "uranium",
    "Lithium": "lithium",
    "Nickel": "nickel",
    "Phosphate": "phosphate",
    "Graphite": "graphite",
    "Zinc": "zinc",
    "Antimony": "antimony",
}

DEFAULT_COMMODITIES: List[str] = ["Gold", "Silver", "Platinum", "Copper", "Uranium"]

COMMODITY_COLOR_MAP: Dict[str, str] = {
    "Gold": "#D4AF37",
    "Silver": "#C0C0C0",
    "Platinum": "#9FA7B2",
    "Copper": "#B87333",
    "Uranium": "#6B8E23",
    "Lithium": "#4F86C6",
    "Nickel": "#6E7F80",
    "Phosphate": "#7EA04D",
    "Graphite": "#4A4A4A",
    "Zinc": "#7D8CA3",
    "Antimony": "#A67C52",
}

TIMEFRAME_OPTIONS: Dict[str, str] = {
    "Past 1 week": "now 7-d",
    "Past 1 month": "today 1-m",
    "Past 3 months": "today 3-m",
    "Past 6 months": "custom-6m",
    "Past 12 months": "today 12-m",
    "Past 5 years": "today 5-y",
    "2004 to present": "all",
}

MENU_ITEMS: List[str] = ["HOME", "INVESTMENTS", "COMMODITIES SENTIMENT"]

from pathlib import Path
import os
from dotenv import load_dotenv

_base = Path(__file__).resolve().parent.parent
# Load .env first; fall back to .env.example so keys work in either file
load_dotenv(_base / ".env", override=False)
load_dotenv(_base / ".env.example", override=False)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
DATA_METADATA = BASE_DIR / "data" / "metadata"

# Source data lives outside the repo structure — resolved at runtime
TIVA_SOURCE = Path(os.getenv(
    "TIVA_DATA_DIR",
    str(BASE_DIR.parent / "TiVA_indicators" / "2026_prel_update")
))

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-3-mini")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-72B-Instruct")

def active_llm_provider() -> tuple[str, str, str] | tuple[None, None, None]:
    """Return (provider_name, api_key, model) for first available key.
    Priority: HuggingFace -> Grok -> Gemini.
    Reads env vars at call time so hot-adding a key works without restart."""
    load_dotenv(_base / ".env", override=False)
    load_dotenv(_base / ".env.example", override=False)
    key_h = os.getenv("HUGGINGFACE_API_KEY", "")
    key_x = os.getenv("GROK_API_KEY", "")
    key_g = os.getenv("GEMINI_API_KEY", "")
    if key_h:
        return "huggingface", key_h, os.getenv("HF_MODEL", HF_MODEL)
    if key_x:
        return "grok", key_x, os.getenv("GROK_MODEL", GROK_MODEL)
    if key_g:
        return "gemini", key_g, os.getenv("GEMINI_MODEL", GEMINI_MODEL)
    return None, None, None

# ── Dataset descriptors ────────────────────────────────────────────────────────
DATASETS = {
    "dmst_va_in_frgn_dmnd": {
        "label": "Domestic VA in Foreign Demand",
        "short": "Domestic VA exported",
        "unit": "% of total services exports",
        "mode_cols": ["Mode 1/4", "Mode 2", "Mode 3"],
        "has_isic": False,
        "description": (
            "Share of domestic value added that is embodied in foreign final demand, "
            "broken down by GATS mode of supply. Measures how a country's domestic "
            "services production reaches foreign markets."
        ),
    },
    "frgn_va_in_dmst_dmnd": {
        "label": "Foreign VA in Domestic Demand",
        "short": "Foreign VA imported",
        "unit": "% of total services imports",
        "mode_cols": ["Mode 1/4", "Mode 2", "Mode 3"],
        "has_isic": False,
        "description": (
            "Share of foreign value added embodied in domestic final demand, "
            "decomposed by mode of supply. Reflects how domestic consumption is "
            "served by foreign services providers."
        ),
    },
    "gvc_participation": {
        "label": "GVC Participation",
        "short": "GVC participation index",
        "unit": "% of gross exports",
        "mode_cols": [
            "Backward (Cross-border)", "Backward (Mode 3)",
            "Forward (Cross-border)", "Forward (Mode 3)",
        ],
        "has_isic": False,
        "description": (
            "Global value chain participation decomposed into backward (foreign VA "
            "in exports) and forward (domestic VA in partners' exports) linkages, "
            "each split between cross-border trade and Mode 3 (commercial presence)."
        ),
    },
    "va_in_mnf_export": {
        "label": "VA in Manufacturing Export",
        "short": "VA in manufacturing exports",
        "unit": "% of manufacturing exports",
        "mode_cols": [
            "Domestic content",
            "Foreign content (Mode 1/4)",
            "Foreign content (Mode 3)",
        ],
        "has_isic": False,
        "description": (
            "Value-added content of manufacturing exports, decomposed into domestic "
            "content and foreign content arriving via cross-border supply (Mode 1/4) "
            "or commercial presence (Mode 3)."
        ),
    },
    "mos3_to_xborder_ratio": {
        "label": "Mode 3 to Cross-border Ratio",
        "short": "Mode 3 / cross-border ratio",
        "unit": "ratio",
        "mode_cols": ["MOS3_to_xborder"],
        "has_isic": True,
        "description": (
            "Ratio of Mode 3 (commercial presence / foreign affiliates) services trade "
            "to cross-border services trade, by sector. Values above 1 indicate that "
            "commercial presence dominates cross-border delivery for that sector."
        ),
    },
}

# ── ISO-3 → country name lookup ───────────────────────────────────────────────
ISO3_NAMES: dict[str, str] = {
    "AGO": "Angola", "ARE": "United Arab Emirates", "ARG": "Argentina",
    "AUS": "Australia", "AUT": "Austria", "BEL": "Belgium",
    "BGD": "Bangladesh", "BGR": "Bulgaria", "BLR": "Belarus",
    "BRA": "Brazil", "BRN": "Brunei Darussalam", "CAN": "Canada",
    "CHE": "Switzerland", "CHL": "Chile", "CHN": "China",
    "CIV": "Côte d'Ivoire", "CMR": "Cameroon", "COD": "Congo, Dem. Rep.",
    "COL": "Colombia", "CRI": "Costa Rica", "CYP": "Cyprus",
    "CZE": "Czech Republic", "DEU": "Germany", "DNK": "Denmark",
    "EGY": "Egypt", "ESP": "Spain", "EST": "Estonia",
    "EU27": "European Union (27)", "FIN": "Finland", "FRA": "France",
    "GBR": "United Kingdom", "GRC": "Greece", "HKG": "Hong Kong SAR",
    "HRV": "Croatia", "HUN": "Hungary", "IDN": "Indonesia",
    "IND": "India", "IRL": "Ireland", "ISL": "Iceland",
    "ISR": "Israel", "ITA": "Italy", "JOR": "Jordan",
    "JPN": "Japan", "KAZ": "Kazakhstan", "KHM": "Cambodia",
    "KOR": "Korea", "LAO": "Lao PDR", "LTU": "Lithuania",
    "LUX": "Luxembourg", "LVA": "Latvia", "MAR": "Morocco",
    "MEX": "Mexico", "MLT": "Malta", "MMR": "Myanmar",
    "MYS": "Malaysia", "NGA": "Nigeria", "NLD": "Netherlands",
    "NOR": "Norway", "NZL": "New Zealand", "PAK": "Pakistan",
    "PER": "Peru", "PHL": "Philippines", "POL": "Poland",
    "PRT": "Portugal", "ROU": "Romania", "ROW": "Rest of World",
    "RUS": "Russia", "SAU": "Saudi Arabia", "SEN": "Senegal",
    "SGP": "Singapore", "STP": "São Tomé and Príncipe", "SVK": "Slovak Republic",
    "SVN": "Slovenia", "SWE": "Sweden", "THA": "Thailand",
    "TUN": "Tunisia", "TUR": "Türkiye", "TWN": "Chinese Taipei",
    "UKR": "Ukraine", "USA": "United States", "VNM": "Viet Nam",
    "ZAF": "South Africa",
}

# ── ISIC code → sector name lookup ────────────────────────────────────────────
ISIC_NAMES: dict[str, str] = {
    "F41T43": "Construction",
    "G45T47": "Wholesale & retail trade",
    "H49":    "Land transport",
    "H50":    "Water transport",
    "H51":    "Air transport",
    "H52":    "Warehousing & support for transport",
    "H53":    "Postal & courier activities",
    "I55T56": "Accommodation & food services",
    "J58T60": "Publishing, broadcasting & media",
    "J61":    "Telecommunications",
    "J62T63": "IT & computer services",
    "K64T66": "Financial & insurance services",
    "L68":    "Real estate",
    "M69T75": "Professional & business services",
    "N77T82": "Administrative & support services",
    "P85":    "Education",
    "Q86T88": "Health & social work",
    "R90T93": "Arts, entertainment & recreation",
    "S94T96": "Other personal services",
}

OECD_BLUE = "#003087"
OECD_LIGHT_BLUE = "#0070C0"
OECD_GREY = "#6D6E71"
OECD_LIGHT_GREY = "#F2F2F2"

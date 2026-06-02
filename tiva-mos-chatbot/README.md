# TiVA-MoS Explorer

A professional Streamlit dashboard and chatbot for exploring OECD Trade in Value-Added
indicators by Mode of Supply (TiVA-MoS).

## What it does

- Visualises 5 TiVA-MoS indicators across 82 economies, 24 years, and up to 19 service sectors
- Decomposes services trade by GATS modes (Mode 1/4 cross-border, Mode 2 consumption abroad, Mode 3 commercial presence)
- Provides a natural-language chatbot grounded in the dataset (no hallucinated values)
- Supports multi-provider LLM fallback: Gemini → Grok → HuggingFace (free tiers)

## Dataset

Source: OECD TiVA-MoS 2026 preliminary release (`2026_prel_update` folder)

| File | Indicator | Years |
|---|---|---|
| `dmst_va_in_frgn_dmnd.csv` | Domestic VA in Foreign Demand | 2000, 2023 |
| `frgn_va_in_dmst_dmnd.csv` | Foreign VA in Domestic Demand | 2000, 2023 |
| `gvc_participation.csv` | GVC Participation | 2000, 2023 |
| `va_in_mnf_export.csv` | VA in Manufacturing Export | 2000, 2023 |
| `mos3_to_xborder_ratio.csv` | Mode 3 / Cross-border Ratio | 2000–2023 |

## Setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

## Data location

By default the app looks for data at:
```
../TiVA_indicators/2026_prel_update/
```
(one level above the project folder, matching the repo layout).

Override with an environment variable:
```
TIVA_DATA_DIR=C:\path\to\your\2026_prel_update
```

## Environment variables

Copy `.env.example` to `.env` and fill in at least one LLM key:

```
GEMINI_API_KEY=your_key_here        # Google AI Studio (recommended — best free tier)
GROK_API_KEY=your_key_here          # xAI Grok
HUGGINGFACE_API_KEY=your_key_here   # HuggingFace Inference API
```

The app runs without any key in analytical mode (queries + charts, no LLM narration).

## Run

```bash
streamlit run app.py
```

## How the chatbot works

**Layer A — deterministic:**
1. Intent classification (trend, top-n, mode shares, compare, define, sector)
2. Entity extraction (country, mode, sector, year) with fuzzy matching
3. Query plan construction
4. DuckDB/pandas query execution
5. Result returned as DataFrame

**Layer B — LLM explanation (optional):**
- Takes the Layer A result as context
- LLM only narrates computed numbers; it cannot invent values
- Provider tried in order: Gemini 2.0 Flash → Grok 3 Mini → Qwen2.5-72B

## Adding new datasets

1. Drop the new CSV in `../TiVA_indicators/2026_prel_update/`
2. Add an entry to `DATASETS` in `src/config.py` with the column names
3. The data loader will pick it up automatically on next startup

## Tests

```bash
pytest tests/ -v
```

## Known limitations

- `2026_prel_update` wide-format files only contain 2 years (2000 and 2023); time-series charts for these indicators show start vs end only
- `mos3_to_xborder_ratio` has the full 2000–2023 series
- No bilateral reporter×partner dimension in current data (single-reporter structure)
- Fuzzy entity matching may occasionally resolve to the wrong country; verify with filter chips

## Structure

```
tiva-mos-chatbot/
├── app.py                  # Streamlit entry point
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py           # Paths, dataset descriptors, ISO3/ISIC lookups, LLM config
│   ├── data_loader.py      # CSV loading, wide→long melt, DuckDB registration
│   ├── query_engine.py     # All analytical queries (filter, top-n, growth, shares…)
│   ├── charts.py           # Plotly chart functions
│   ├── chatbot.py          # Intent→query→LLM pipeline
│   ├── prompts.py          # LLM prompt templates and terminology definitions
│   └── ui_components.py    # Streamlit layout helpers
├── assets/theme.css        # OECD-style CSS
└── tests/
    ├── test_data_loader.py
    └── test_query_engine.py
```

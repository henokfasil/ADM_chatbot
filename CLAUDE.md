# CLAUDE.md — Project Memory for Claude Code

This file gives Claude Code full context about this repository so future sessions
start with complete understanding. Read this before writing any code.

---

## Repository overview

```
ADM_chatbot/                          ← Git root (GitHub: henokfasil/ADM_chatbot)
├── TiVA_indicators/
│   └── 2026_prel_update/             ← RAW DATA (5 CSV files, never touch)
│       ├── dmst_va_in_frgn_dmnd.csv  ← Domestic VA in Foreign Demand (164 rows)
│       ├── frgn_va_in_dmst_dmnd.csv  ← Foreign VA in Domestic Demand (164 rows)
│       ├── gvc_participation.csv     ← GVC Participation (164 rows)
│       ├── va_in_mnf_export.csv      ← VA in Manufacturing Export (164 rows)
│       └── mos3_to_xborder_ratio.csv ← Mode 3/Cross-border Ratio (37,392 rows)
│
├── tiva-mos-chatbot/                 ← App 1: Chat & Vizboard (prototype)
│   ├── app.py                        ← Entry point: 25%/75% split layout
│   ├── .env                          ← REAL API KEYS — never commit
│   ├── src/
│   │   ├── config.py                 ← Paths, DATASETS dict, ISO3/ISIC lookups
│   │   ├── data_loader.py            ← CSV→long format, DuckDB registration
│   │   ├── query_engine.py           ← filter_data, top_n, growth, mode_shares
│   │   ├── chatbot.py                ← Intent→query→LLM pipeline
│   │   ├── charts.py                 ← Plotly chart functions
│   │   ├── prompts.py                ← LLM prompt templates + metadata defs
│   │   └── ui_components.py          ← render_header, render_inline_filters, etc.
│   └── assets/theme.css
│
└── tiva-mos-ai-analyst/              ← App 2: AI Analyst (new, production)
    ├── app.py                        ← Entry point: sidebar + 7 tabs
    ├── .env.example                  ← Template (no keys)
    ├── metadata/
    │   ├── indicators.yml            ← Full indicator defs, synonyms, policy context
    │   └── synonyms.yml              ← NL→dataset/mode/sector resolution
    ├── services/
    │   ├── data_loader.py            ← Same CSV loading, lru_cache, DuckDB
    │   ├── query_interpreter.py      ← YAML-based intent+entity extraction
    │   ├── ai_response.py            ← Orchestrator: plan→data→chart→LLM
    │   ├── chart_generator.py        ← smart_chart() auto-selects chart type
    │   ├── policy_interpreter.py     ← LLM call + structured response parser
    │   └── export_service.py         ← CSV, text, policy note generator
    ├── components/
    │   ├── header.py                 ← Institutional OECD header
    │   ├── ai_analyst.py             ← 3-column AI workspace tab
    │   ├── dashboard_tabs.py         ← Exec Summary, Explorer, Compare, Mode&Sector
    │   ├── data_dictionary.py        ← Searchable YAML-driven dictionary
    │   └── export_tools.py           ← Export Center tab
    ├── utils/formatting.py
    └── assets/theme.css
```

---

## How to run locally

**App 1 (Chat & Vizboard) — port 8501:**
```powershell
$STREAMLIT = "C:\Users\telila_h\AppData\Roaming\Python\Python312\Scripts\streamlit.exe"
& $STREAMLIT run "c:\Users\telila_h\OneDrive - OECD\OECD files\Chatbot_ADM\tiva-mos-chatbot\app.py" --server.port 8501
```

**App 2 (AI Analyst) — port 8502:**
```powershell
& $STREAMLIT run "c:\Users\telila_h\OneDrive - OECD\OECD files\Chatbot_ADM\tiva-mos-ai-analyst\app.py" --server.port 8502
```

**Python:** `P:\Python\3.12.7\python.exe`
**pip:** `P:\Python\3.12.7\Scripts\pip.exe`
**Packages installed:** user-level at `C:\Users\telila_h\AppData\Roaming\Python\Python312\site-packages\`

---

## API keys (stored in tiva-mos-chatbot/.env)

Priority order: **HuggingFace → Grok → Gemini**

- `HUGGINGFACE_API_KEY` — Qwen/Qwen2.5-72B-Instruct via chat completions API
- `GROK_API_KEY` — grok-3-mini via OpenAI-compatible endpoint (https://api.x.ai/v1)
- `GEMINI_API_KEY` — gemini-2.5-flash via google-genai SDK

The `tiva-mos-ai-analyst` app reads keys from `tiva-mos-chatbot/.env` as fallback.
Never read/print the actual key values in responses.

---

## Streamlit Cloud deployments

Both apps live in the same GitHub repo: `henokfasil/ADM_chatbot`

| App | Main file path | Secrets |
|-----|---------------|---------|
| Chat & Vizboard | `tiva-mos-chatbot/app.py` | HUGGINGFACE_API_KEY, GROK_API_KEY, GEMINI_API_KEY, GEMINI_MODEL |
| AI Analyst | `tiva-mos-ai-analyst/app.py` | Same keys |

---

## Critical patterns learned (do not repeat past mistakes)

### Encoding
- **Never put emoji in Python string literals** (dict values, f-strings, function args).
  They corrupt on Windows→GitHub→Linux pipeline. Only use emoji inside HTML strings
  passed to `st.markdown(..., unsafe_allow_html=True)` or as HTML entities `&#128172;`.
- Add `# -*- coding: utf-8 -*-` to any file touched by emoji/Unicode.

### Streamlit HTML rendering
- **Never join multiple HTML blocks into one big `st.markdown()` call.**
  Streamlit's markdown parser truncates long/nested HTML mid-way and renders
  the rest as raw text. Always use separate `st.markdown()` calls per element.
- Example: metric cards → use `st.columns()` + individual `.markdown()` per card.

### Button handlers and expensive calls
- **Never call an LLM API or slow function inside a button handler that's
  inside `st.columns()`**. It fails silently on Streamlit Cloud.
- Correct pattern: button sets `st.session_state["pending_question"] = q` then
  `st.rerun()`. The expensive call runs at the TOP of the component function,
  before any columns, on the next rerun.

### PowerShell file editing
- **Never use PowerShell `Set-Content` or regex on Python source files.**
  It corrupts encoding (LF→CRLF + UTF-8 BOM). Always use the Edit/Write tools.

### Data notes
- `2026_prel_update` wide files have only **2 years: 2000 and 2023**.
  Only `mos3_to_xborder_ratio` has the full 2000–2023 annual series.
- The canonical long format has columns:
  `dataset_name, year, geo, country_name, isic_code, sector_name, mode_name, value`

---

## User preferences

- Concise, direct responses — no lengthy preambles
- Push to GitHub after every significant change
- Both local restart and git push in same step
- Prefer Edit tool over Write for existing files
- No emoji in Python code; HTML entities in HTML strings only
- App titles: "TiVA-MoS Chat & Vizboard" and "TiVA-MoS AI Analyst"
- LLM priority: HuggingFace first (open-source positioning), then Grok, then Gemini

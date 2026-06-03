# TiVA-MoS AI Analyst — Technical Context Note

**How we built it, what it does, and why it works the way it does.**

Prepared for colleagues asking: *"How did you do this?"*

---

## What was built

Two Streamlit-based analytical web applications on top of the OECD
TiVA-MoS 2026 Preliminary Release dataset:

| App | Purpose | URL pattern |
|-----|---------|-------------|
| **TiVA-MoS Chat & Vizboard** | Prototype: chatbot + dashboard split-pane | `tiva-mos-chatbot/` |
| **TiVA-MoS AI Analyst** | Production: AI-assisted analytical workspace | `tiva-mos-ai-analyst/` |

Both are deployed publicly on **Streamlit Community Cloud** (free tier),
connected to a public GitHub repository.

---

## Dataset

**Source:** OECD TiVA-MoS 2026 Preliminary Release (`2026_prel_update` folder)

Five CSV files:

| File | Indicator | Coverage |
|------|-----------|----------|
| `dmst_va_in_frgn_dmnd.csv` | Domestic VA in Foreign Demand | 82 economies, 2000 & 2023 |
| `frgn_va_in_dmst_dmnd.csv` | Foreign VA in Domestic Demand | 82 economies, 2000 & 2023 |
| `gvc_participation.csv` | GVC Participation | 82 economies, 2000 & 2023 |
| `va_in_mnf_export.csv` | VA in Manufacturing Export | 82 economies, 2000 & 2023 |
| `mos3_to_xborder_ratio.csv` | Mode 3 / Cross-border Ratio | 82 economies × 19 sectors × 2000–2023 |

Data is loaded, melted from wide to long format, and registered as DuckDB
in-memory views at startup. All analytical queries run locally — no external
database is needed.

---

## Technology stack

| Layer | Technology | Reason chosen |
|-------|-----------|---------------|
| **Web framework** | Streamlit 1.58 | Rapid Python dashboard deployment, free hosting |
| **Data processing** | pandas 3.0 | Wide-to-long transformation, filtering |
| **Analytical queries** | DuckDB 1.5 | Fast in-memory SQL over pandas DataFrames |
| **Visualisation** | Plotly 6 | Interactive charts, OECD-style theming |
| **NLP / fuzzy matching** | RapidFuzz | Country and sector name resolution from free text |
| **Semantic metadata** | YAML (PyYAML) | Human-readable indicator definitions and synonym maps |
| **LLM inference** | HuggingFace Inference API (Qwen2.5-72B-Instruct) | Free tier, open-source model, no data leaves to proprietary cloud |
| **LLM fallback** | Grok (xAI) → Gemini 2.5 Flash | Automatic rotation if primary fails |
| **Deployment** | Streamlit Community Cloud + GitHub | Free, git-connected, no server management |

**Total cloud cost: $0.** All LLM providers used are on free tiers.

---

## Architecture: TiVA-MoS AI Analyst

The AI Analyst follows a **two-layer grounded AI design**:

```
User question
      │
      ▼
┌─────────────────────────────────────────────────┐
│  LAYER A — Deterministic Query Engine           │
│                                                 │
│  1. Query Interpreter (query_interpreter.py)    │
│     • Detects intent: rank / compare / trend /  │
│       explain / mode_shares / policy            │
│     • Resolves entities via YAML synonym maps:  │
│       "commercial presence" → Mode 3            │
│       "France" → FRA                            │
│       "telecoms" → J61 (ISIC code)             │
│     • Detects ambiguity; asks clarification     │
│     • Returns structured QueryPlan object       │
│                                                 │
│  2. Data Executor (ai_response.py)              │
│     • Filters canonical DataFrame by QueryPlan  │
│     • Returns verified pandas DataFrame         │
│     • No LLM involved; values are exact         │
│                                                 │
│  3. Chart Generator (chart_generator.py)        │
│     • smart_chart() picks best chart type       │
│       by inspecting data shape + intent         │
│     • Returns Plotly Figure                     │
└─────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────┐
│  LAYER B — LLM Explanation Layer               │
│                                                 │
│  4. Policy Interpreter (policy_interpreter.py)  │
│     • Passes Layer A result to LLM              │
│     • LLM only narrates what Layer A computed   │
│     • Structured output: Answer / Policy        │
│       Interpretation / Caveat / Follow-up Qs    │
│     • If LLM fails → falls back to template     │
│                                                 │
│  Provider rotation: HuggingFace → Grok → Gemini │
└─────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────┐
│  OUTPUT CANVAS (ai_analyst.py)                  │
│                                                 │
│  • Direct answer (from LLM, grounded on data)   │
│  • Interactive Plotly chart                     │
│  • Collapsible data table                       │
│  • Policy interpretation box                    │
│  • Evidence & provenance box (filters used)     │
│  • Export buttons: CSV / text / policy note     │
│  • Follow-up question suggestions               │
└─────────────────────────────────────────────────┘
```

### Why this design matters

The LLM **never sees the raw data** and **never fabricates values**.
It only receives the summary of what the query engine already computed
and is asked to narrate it in plain language. This is the key architectural
decision that makes the tool safe for OECD analytical use.

---

## Semantic metadata layer

Rather than hard-coding everything in Python, indicator knowledge lives in
human-readable YAML files:

**`metadata/indicators.yml`** — for each indicator:
- Full definition (short + long)
- Unit, valid years, available modes
- Policy context (what the indicator implies)
- Caveats (data limitations)
- Synonyms (what users might call it in natural language)

**`metadata/synonyms.yml`** — resolves natural language to canonical values:
```yaml
modes:
  "commercial presence": "Mode 3"
  "foreign affiliates":  "Mode 3"
  "cross-border":        "Mode 1/4"

sectors:
  "telecom": "J61"
  "finance": "K64T66"
  "IT":      "J62T63"
```

This means the app understands "show commercial presence for France" without
any machine learning — just dictionary lookup + fuzzy matching.

---

## UI design principles

**OECD institutional style:**
- Deep navy (`#0D1B4B`) + OECD blue (`#003087`) + light blue (`#0055A5`)
- Inter typeface (clean, professional)
- White cards with soft shadows
- No rainbow charts — all Plotly charts use the OECD blue palette

**Three-column AI workspace:**
```
┌──────────────┬──────────────────────────┬──────────────┐
│ Control      │ Output Canvas            │ Provenance   │
│ (25%)        │ (50%)                    │ (25%)        │
│              │                          │              │
│ Ask box      │ Answer                   │ Evidence box │
│ Prompt       │ Chart                    │ Filters used │
│ groups       │ Policy interpretation    │ Indicator    │
│              │ Export buttons           │ definition   │
│ Explain      │ Follow-up suggestions    │ Caveats      │
│ Rank         │                          │              │
│ Compare      │                          │              │
│ Trend        │                          │              │
│ Policy       │                          │              │
└──────────────┴──────────────────────────┴──────────────┘
```

---

## Export capability

Every analytical result can be exported as:
- **CSV** — filtered data table
- **Text answer** — the AI's full response with filters and caveats
- **One-page policy note** — structured document with: question, finding,
  chart reference, policy interpretation, data source, caveat, disclaimer

---

## Deployment: zero-cost, zero-ops

```
Local code (VS Code / Claude Code)
        │
        ▼ git push
GitHub repo (henokfasil/ADM_chatbot)
        │
        ▼ auto-deploy
Streamlit Community Cloud
        │
        ├── App 1: tiva-mos-chatbot/app.py
        └── App 2: tiva-mos-ai-analyst/app.py
```

Streamlit Cloud watches the GitHub repo and redeploys automatically on every push.
API keys are stored securely as Streamlit secrets (not in the repository).
The data files are committed to the repository (they are small enough: ~3 MB total).

---

## What makes this technically interesting

1. **Grounded AI** — The LLM cannot hallucinate values because it only receives
   pre-computed results. The data pipeline and LLM layer are architecturally separated.

2. **Free-tier multi-provider LLM** — HuggingFace (Qwen 72B open-source model)
   → Grok → Gemini, with automatic fallback. Total inference cost: $0.

3. **YAML semantic layer** — Indicator knowledge and synonym maps are in editable
   YAML files, not buried in Python code. A domain expert can update definitions
   without touching code.

4. **Smart chart selection** — `smart_chart()` inspects the data's column structure
   and the detected intent to automatically pick the right chart type without
   the user specifying it.

5. **Query plan architecture** — Every natural language question is parsed into
   a structured `QueryPlan` object before any data is touched. This makes the
   reasoning auditable and testable.

6. **Policy note export** — The app generates a formatted one-page analytical
   note ready for internal circulation, including data provenance and caveats.

---

## Limitations to be transparent about

- The 4 wide-format indicators only have **2 time points** (2000 and 2023) in this
  release. Only the Mode 3/Cross-border Ratio has the full 2000–2023 annual series.
- No bilateral reporter×partner dimension in current data.
- The chatbot uses keyword-based intent classification (not ML). Unusual phrasings
  may misroute, though fuzzy matching catches most country/sector name variations.
- LLM responses are constrained but not fully auditable. The evidence box should
  always be checked for the filters actually used.

---

## Files of interest for colleagues

| File | What it does |
|------|-------------|
| `tiva-mos-ai-analyst/services/query_interpreter.py` | How NL questions become structured queries |
| `tiva-mos-ai-analyst/services/policy_interpreter.py` | How LLM prompts are structured to prevent hallucination |
| `tiva-mos-ai-analyst/metadata/indicators.yml` | All indicator definitions and synonyms |
| `tiva-mos-ai-analyst/components/ai_analyst.py` | The main 3-column UI layout |
| `tiva-mos-chatbot/src/chatbot.py` | The prototype chatbot pipeline |

---

*Built with Claude Code (Anthropic) as AI coding assistant.
Dataset: OECD TiVA-MoS 2026 Preliminary Release.*

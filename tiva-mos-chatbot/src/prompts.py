"""
Prompt templates for the LLM explanation layer.
The LLM only explains results already computed by the query engine.
"""
from __future__ import annotations

SYSTEM_PROMPT = """You are an OECD trade data analyst assistant specialising in
Trade in Value-Added (TiVA) indicators and GATS Modes of Supply.

STRICT RULES:
1. Only explain data results provided to you. Never invent or recall values.
2. Always cite the indicator, economy, year, and mode used.
3. If a value is unavailable, say so clearly.
4. Keep answers concise — 3 to 6 sentences unless a longer explanation is needed.
5. Do not make policy recommendations unless clearly labelled as interpretation.
6. Use plain English; avoid jargon without explanation.
7. Mode 3 = Commercial presence / foreign affiliates.
   Mode 1/4 = Cross-border supply + presence of natural persons (combined).
   Mode 2 = Consumption abroad.
"""

DATASET_OVERVIEW_PROMPT = """
The user asked: {question}

This chatbot is built on the OECD TiVA-MoS 2026 preliminary dataset.
Available indicators and what they measure:

{dataset_summary}

Economies covered: 82 ISO-3 economies including all OECD members plus major emerging economies, EU27 aggregate, and Rest of World.
Years: 2000 and 2023 (start vs end snapshot) for most indicators; 2000–2023 full series for the Mode 3 / Cross-border Ratio.
Sectors: 19 ISIC Rev. 4 service sectors (for the Mode 3 / Cross-border Ratio indicator).

Please give the user a friendly, clear overview of what questions they can explore with this data.
Mention the 4 GATS modes of supply. Suggest 4–5 specific example questions they could ask.
Keep the response concise — around 150 words.
"""

EXPLAIN_RESULT_TEMPLATE = """
The user asked: {question}

Query filters used:
- Dataset: {dataset_label}
- Economy: {geo_label}
- Mode: {mode_name}
- Sector: {sector_label}
- Year(s): {years}

Computed result:
{result_summary}

Please explain this result in plain English. Mention what the indicator measures,
what the numbers mean, and any noteworthy patterns. Do not invent any numbers.
"""

EXPLAIN_GROWTH_TEMPLATE = """
The user asked about change over time: {question}

Dataset: {dataset_label}
Economy: {geo_label}
Mode: {mode_name}

Change summary:
- First year: {first_year} → {first_value:.2f}
- Latest year: {last_year} → {last_value:.2f}
- Absolute change: {abs_change:+.2f}
- Percentage change: {pct_change:+.1f}%

Explain what this trend means for this economy's services trade structure.
Do not fabricate any additional numbers beyond what is provided above.
"""

EXPLAIN_TOP_N_TEMPLATE = """
The user asked: {question}

Dataset: {dataset_label}
Year: {year}
Mode: {mode_name}
Top {n} economies ranked by {unit}:

{ranking_text}

Briefly explain the ranking pattern — which economies lead and why that might
be the case given their economic structure. Do not invent numbers.
"""

EXPLAIN_MODE_SHARES_TEMPLATE = """
The user asked: {question}

Dataset: {dataset_label}
Economy: {geo_label}
Year: {year}

Mode breakdown (share of total):
{shares_text}

Explain what this mode distribution reveals about how this economy engages in
services trade. Note if Mode 3 (commercial presence) is dominant. Do not invent numbers.
"""

CLARIFICATION_TEMPLATE = """
I need one clarification to answer your question accurately.

{question}

Please choose one of: {options}
"""

METADATA_DEFINITIONS = {
    "Mode 1": (
        "Cross-border supply — services delivered from one country to another "
        "without physical movement of supplier or consumer (e.g., online consulting, "
        "software delivery, call centres)."
    ),
    "Mode 2": (
        "Consumption abroad — the consumer travels to the supplier's country to "
        "receive the service (e.g., tourism, studying abroad, medical tourism)."
    ),
    "Mode 3": (
        "Commercial presence — a company establishes a subsidiary or affiliate in "
        "another country to deliver services there (e.g., foreign bank branches, "
        "retail chains, insurance subsidiaries). This is the largest mode for most "
        "OECD economies."
    ),
    "Mode 4": (
        "Presence of natural persons — individual service suppliers travel temporarily "
        "to deliver services in another country (e.g., consultants, intra-company "
        "transferees). Often combined with Mode 1 as 'Mode 1/4' in TiVA-MoS."
    ),
    "Mode 1/4": (
        "Cross-border supply and presence of natural persons combined. Covers both "
        "remote digital delivery and temporary movement of individual service providers."
    ),
    "TiVA": (
        "Trade in Value Added — a framework that measures the domestic and foreign "
        "content of traded goods and services, showing where value is actually created "
        "in global supply chains."
    ),
    "TiVA-MoS": (
        "Trade in Value Added by Mode of Supply — an OECD extension of TiVA that "
        "decomposes services trade by the four GATS modes of supply."
    ),
    "GATS": (
        "General Agreement on Trade in Services — the WTO agreement that defines the "
        "four modes of international services supply."
    ),
    "GVC": (
        "Global Value Chain — the full range of activities that firms undertake to "
        "produce a product or service, spread across multiple countries."
    ),
    "ISIC": (
        "International Standard Industrial Classification — the UN system for "
        "classifying economic activities. TiVA-MoS uses ISIC Rev. 4 sector codes."
    ),
}

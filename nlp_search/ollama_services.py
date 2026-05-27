import json
import re
import requests
from psycopg2.extras import RealDictCursor

from repository.respository_connection import get_connection

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
# ───────────────────────────────────────────────────────────────────────────────

SCHEMA = """
Table: italy_companies_master_list

String columns:
  denominazione       : company name
  comune              : city (e.g. 'ROMA', 'MILANO')
  forma_giuridica     : legal form
  codice_ateco        : sector code (e.g. '66.22.00')
  amministratore_2, amministratore_3, amministratore_4, amministratore_5
  socio_1, socio_2, socio_3, socio_4, socio_5

Numeric columns (replace <year> with 2022, 2023, or 2024):
  ricavi_operativi_<year>
  totale_valore_produzione_<year>
  totale_costi_produzione_<year>
  ammortamenti_e_svalutazioni_<year>
  ebit_<year>
  immobilizzazioni_immateriali_<year>
  immobilizzazioni_materiali_<year>
  crediti_verso_clienti_<year>
  disponibilita_liquide_<year>
  totale_debiti_<year>
  debiti_entro_12_mesi_<year>
  debiti_oltre_12_mesi_<year>
  trattamento_fine_rapporto_<year>
  numero_dipendenti_<year>
  costo_personale_<year>
"""

PROMPT_TEMPLATE = """You are a PostgreSQL query generator for an Italian company database.

SCHEMA:
{schema}

USER QUERY: "{query}"

IMPORTANT:
- Return ONLY a single valid JSON object. No explanation. No markdown. No extra text.
- Never use SELECT *  — always return only: id, denominazione, comune, codice_ateco
- Always use parameterized-style values inside the JSON (not inline SQL injection)
- Default year is 2024 if not specified

Return this exact JSON structure:

{{
  "where": "ebit_2023 > 1000000",
  "order_by": "ebit_2023 DESC",
  "limit": 3
}}

Rules:
- "where" : valid PostgreSQL WHERE clause (without the word WHERE). Use AND/OR as needed. For no filter use "1=1"
- "order_by" : column + ASC/DESC, or null if no sorting needed
- "limit" : integer or null
- For "top N by X"    → order_by = "X DESC", limit = N, where = "1=1"
- For "bottom N by X" → order_by = "X ASC",  limit = N, where = "1=1"
- For city filter     → comune = 'ROMA'  (always UPPERCASE string)
- For name search     → denominazione ILIKE '%keyword%'
- For socio/shareholder search → (socio_1 ILIKE '%name%' OR socio_2 ILIKE '%name%' OR socio_3 ILIKE '%name%' OR socio_4 ILIKE '%name%' OR socio_5 ILIKE '%name%')
- For admin search    → (amministratore_2 ILIKE '%name%' OR amministratore_3 ILIKE '%name%' OR amministratore_4 ILIKE '%name%' OR amministratore_5 ILIKE '%name%')
- For growth queries  → use: (to_year_col - from_year_col) / NULLIF(ABS(from_year_col), 0) * 100 > percent
- "15 million" = 15000000, "1.5 million" = 1500000
- Return ONLY the JSON object, nothing else
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text)
    text = text.replace("```", "").strip()

    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in LLM response:\n{text}")

    depth = 0
    in_string = False
    escape = False

    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON block: {e}\n{candidate}")

    raise ValueError(f"Could not find complete JSON in:\n{text}")


def _sanitize_where(where: str) -> str:
    """
    Basic safety check — block obviously dangerous SQL keywords.
    LLM output is never fully trusted.
    """
    blocked = ["drop", "delete", "insert", "update", "truncate",
               "alter", "create", "exec", "execute", "--", ";"]
    lower = where.lower()
    for word in blocked:
        if word in lower:
            raise ValueError(f"Unsafe SQL keyword detected in WHERE clause: '{word}'")
    return where


# ── Ollama call ────────────────────────────────────────────────────────────────

def _ask_ollama(query: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(schema=SCHEMA, query=query)
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot reach Ollama at localhost:11434.\n"
            "Make sure Ollama is running: ollama serve\n"
            f"Then pull a model: ollama pull {OLLAMA_MODEL}"
        )

    raw_text = resp.json().get("response", "")
    return _extract_json(raw_text)


# ── Main search function ───────────────────────────────────────────────────────

def search(query: str) -> list[dict]:
    print(f"\n🔍 Query: {query}")

    # 1. Ask LLM for SQL fragments only
    plan = _ask_ollama(query)
    print(f"📋 SQL plan:\n{json.dumps(plan, indent=2, ensure_ascii=False)}\n")

    # 2. Extract and sanitize
    where    = _sanitize_where(plan.get("where") or "1=1")
    order_by = plan.get("order_by")
    limit    = plan.get("limit")

    # 3. Build final SQL — DB does all the heavy lifting
    sql = f"""
        SELECT id, denominazione, comune, codice_ateco
        FROM italy_companies_master_list
        WHERE {where}
    """
    if order_by:
        sql += f" ORDER BY {order_by}"

    if limit:
        try:
            sql += f" LIMIT {int(limit)}"
        except (ValueError, TypeError):
            pass

    print(f"📝 SQL:\n{sql.strip()}\n")

    # 4. Run against DB — no data ever loaded into memory
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            results = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    print(f"✅ {len(results)} result(s) found.")
    return results
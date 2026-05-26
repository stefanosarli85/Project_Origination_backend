import json
import re
import requests

from services.region.italy.ReportAziende.italy_region_service import get_all_records_italy

# ── Config ─────────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"
# ───────────────────────────────────────────────────────────────────────────────

SCHEMA = """
String fields (use == for exact match, 'in' for contains):
  denominazione        : company name
  comune               : city (e.g. ROMA, MILANO)
  forma_giuridica      : legal form (e.g. contains RESPONSABILITA for SRL)
  codice_ateco         : sector code (e.g. 66.22.00)
  amministratore_2..5  : administrator names
  socio_1..5           : shareholder names with % (e.g. "BERTINELLI FILIPPO 40%")

Numeric fields (available for years 2022, 2023, 2024):
  ricavi_operativi
  totale_valore_produzione
  totale_costi_produzione
  ammortamenti_e_svalutazioni
  ebit
  immobilizzazioni_immateriali
  immobilizzazioni_materiali
  crediti_verso_clienti
  disponibilita_liquide
  totale_debiti
  debiti_entro_12_mesi
  debiti_oltre_12_mesi
  trattamento_fine_rapporto
  numero_dipendenti
  costo_personale

For numeric+year fields, the key is: "<field>_<year>"
  e.g. "ricavi_operativi_2024", "ebit_2023", "numero_dipendenti_2022"
"""

PROMPT_TEMPLATE = """You are a data filter generator for an Italian company database.

SCHEMA:
{schema}

USER QUERY: "{query}"

IMPORTANT: Return ONLY a single valid JSON object. No explanation. No markdown. No extra text before or after.

The JSON must have this exact structure (omit keys that are not needed):

{{
  "filters": [
    {{
      "field": "ricavi_operativi_2024",
      "op": "gt",
      "value": 15000000
    }}
  ],
  "sort_by": null,
  "sort_order": null,
  "limit": null,
  "growth": null
}}

Operator values for "op": gt, lt, gte, lte, eq, contains, between
For "between" also include "value2": <number>

For growth queries use this shape (otherwise set growth to null):
  "growth": {{
    "field": "ricavi_operativi",
    "from_year": "2022",
    "to_year": "2024",
    "op": "gt",
    "percent": 10
  }}

Rules:
- For shareholder/socio queries: field = "socio_1", op = "contains"
- For admin queries: field = "amministratore_2", op = "contains"
- For city: field = "comune", op = "eq", value in UPPERCASE
- "15 million" = 15000000, "1.5 million" = 1500000
- Default year is 2024 if not specified
- growth must be null if the query is NOT about growth/increase/change over time
- Return ONLY the JSON object, nothing else
"""


# ── Load data from DB via pagination ──────────────────────────────────────────

def load_data() -> list[dict]:
    """Fetch all records from DB using pagination (100 per page)."""
    all_records = []
    page = 1

    while True:
        batch = get_all_records_italy(page=page)
        if not batch:
            break
        all_records.extend(batch)
        page += 1

    print(f"📦 Loaded {len(all_records)} records from DB.")
    return all_records


# ── Helpers ────────────────────────────────────────────────────────────────────

def _num(company: dict, field: str) -> float | None:
    v = company.get(field)
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


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
                    raise ValueError(f"Found JSON-like block but it's invalid: {e}\n{candidate}")

    raise ValueError(f"Could not find a complete JSON object in:\n{text}")


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


# ── Filter logic ───────────────────────────────────────────────────────────────

OP_MAP = {">": "gt", ">=": "gte", "<": "lt", "<=": "lte", "=": "eq", "==": "eq"}


def _apply_filter(company: dict, f: dict) -> bool:
    field = f.get("field", "")
    op    = OP_MAP.get(f.get("op", ""), f.get("op", ""))
    value = f.get("value")

    if value is None:
        return True

    # String ops
    if op == "contains":
        # Check all socio/amministratore variants e.g. socio_1..5
        base = re.sub(r"_\d+$", "", field)
        for i in range(1, 6):
            cell = str(company.get(f"{base}_{i}", "")).upper()
            if str(value).upper() in cell:
                return True
        cell = str(company.get(field, "")).upper()
        return str(value).upper() in cell

    if op == "eq":
        num = _num(company, field)
        if num is not None:
            try:
                return num == float(str(value).replace(",", ""))
            except (ValueError, TypeError):
                pass
        cell = str(company.get(field, "")).upper()
        return cell == str(value).upper()

    # Numeric ops
    num = _num(company, field)
    if num is None:
        return False

    try:
        val = float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return False

    if op == "gt":  return num >  val
    if op == "gte": return num >= val
    if op == "lt":  return num <  val
    if op == "lte": return num <= val
    if op == "between":
        try:
            val2 = float(str(f.get("value2", value)).replace(",", ""))
        except (ValueError, TypeError):
            return False
        return val <= num <= val2

    return True


def _apply_growth(company: dict, g: dict) -> bool:
    field = g.get("field")
    y1    = g.get("from_year", "2022")
    y2    = g.get("to_year",   "2024")
    op    = OP_MAP.get(g.get("op", "gt"), g.get("op", "gt"))
    pct   = g.get("percent")

    if not field or pct is None:
        return True

    try:
        pct = float(pct)
    except (ValueError, TypeError):
        return True

    v1 = _num(company, f"{field}_{y1}")
    v2 = _num(company, f"{field}_{y2}")
    if v1 is None or v2 is None or v1 == 0:
        return False

    growth = (v2 - v1) / abs(v1) * 100
    if op == "gt":  return growth >  pct
    if op == "gte": return growth >= pct
    if op == "lt":  return growth <  pct
    if op == "lte": return growth <= pct
    return False


# ── Main search function ───────────────────────────────────────────────────────

def search(query: str) -> list[dict]:
    print(f"\n🔍 Query : {query}")

    # 1. Ask local LLM for filter plan
    plan = _ask_ollama(query)
    print(f"📋 Filter plan:\n{json.dumps(plan, indent=2, ensure_ascii=False)}\n")

    # 2. Load all data from DB
    companies = load_data()
    result = list(companies)

    # 3. Apply filters
    for f in plan.get("filters") or []:
        result = [c for c in result if _apply_filter(c, f)]

    # 4. Apply growth filter
    growth = plan.get("growth")
    if isinstance(growth, dict) and growth.get("field") and growth.get("percent") is not None:
        result = [c for c in result if _apply_growth(c, growth)]

    # 5. Sort
    sort_by    = plan.get("sort_by")
    sort_order = plan.get("sort_order") or "desc"
    if sort_by:
        result.sort(
            key=lambda c: _num(c, sort_by) or 0,
            reverse=(sort_order.lower() == "desc"),
        )

    # 6. Limit
    limit = plan.get("limit")
    if limit:
        try:
            result = result[:int(limit)]
        except (ValueError, TypeError):
            pass

    print(f"✅ {len(result)} result(s) found.")
    return result
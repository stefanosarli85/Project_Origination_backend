from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# IMPORTANT: your DB connection
# You said this already exists in your system

import sqlglot

from repository.respository_connection import get_connection

# ----------------------------
# Load SQLCoder
# ----------------------------
MODEL_NAME = "defog/sqlcoder-7b-2"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    device_map="auto",
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
)


# ----------------------------
# Schema (compressed)
# ----------------------------
SCHEMA = """
Table: italy_companies_master_list

Columns:
id, codice_fiscale, partita_iva, denominazione, comune,
forma_giuridica, codice_ateco

Financials (2022-2024):
ricavi_operativi_YYYY,
totale_valore_produzione_YYYY,
totale_costi_produzione_YYYY,
ebit_YYYY,
numero_dipendenti_YYYY,
costo_personale_YYYY,
disponibilita_liquide_YYYY,
totale_debiti_YYYY
"""


# ----------------------------
# Prompt builder
# ----------------------------
def build_prompt(question: str):
    return f"""
You are an expert PostgreSQL SQL generator.

RULES:
- Output ONLY SQL
- Use only provided schema
- Use 2024 columns unless specified
- SELECT queries only
- No explanations

SCHEMA:
{SCHEMA}

QUESTION:
{question}

SQL:
""".strip()


# ----------------------------
# SQL safety check
# ----------------------------
def is_safe_sql(sql: str):
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
        return parsed.key.upper() == "SELECT"
    except:
        return False


# ----------------------------
# Generate SQL
# ----------------------------
def generate_sql(question: str):
    prompt = build_prompt(question)

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=200,
        temperature=0,
        do_sample=False
    )

    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)

    sql = decoded.split("SQL:")[-1].strip()
    return sql


# ----------------------------
# Execute SQL
# ----------------------------
def execute_sql(sql: str):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql)

        # fetch results
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()

        result = [dict(zip(columns, row)) for row in rows]

        conn.commit()

        return result

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cursor.close()
        conn.close()


# ----------------------------
# MAIN PIPELINE
# ----------------------------
def ask_db(question: str):
    print("\n🧠 USER QUESTION:", question)

    # Step 1: Generate SQL
    sql = generate_sql(question)

    print("\n🧾 GENERATED SQL:\n", sql)

    # Step 2: Safety check
    if not is_safe_sql(sql):
        print("\n❌ Unsafe SQL detected. Aborting execution.")
        return None

    # Step 3: Execute SQL
    result = execute_sql(sql)

    # Step 4: Print result
    print("\n📊 QUERY RESULT:")
    for row in result:
        print(row)

    return result


# ----------------------------
# Example usage
# ----------------------------
if __name__ == "__main__":
    ask_db("top 10 companies by revenue in 2024")
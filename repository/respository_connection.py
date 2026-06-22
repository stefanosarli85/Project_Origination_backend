import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="require",
    )



def print_schema():
    conn = get_connection()
    cur = conn.cursor()

    query = """
    SELECT
        table_name,
        column_name,
        data_type,
        is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """

    cur.execute(query)
    rows = cur.fetchall()

    current_table = None

    for table, column, dtype, nullable in rows:
        if table != current_table:
            current_table = table
            print(f"\n=== {table} ===")

        print(f"{column} | {dtype} | nullable={nullable}")

    cur.close()
    conn.close()


import psycopg2
from psycopg2 import sql
import os

from repository.respository_connection import get_connection


def create_italy_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # =========================================================
    # MASTER COMPANY TABLE
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_companies (
            id BIGSERIAL PRIMARY KEY,

            company_code VARCHAR(20) UNIQUE NOT NULL,
            company_name VARCHAR(255),

            partita_iva VARCHAR(20),
            codice_fiscale VARCHAR(20),

            legal_form_class VARCHAR(10),
            legal_form_code VARCHAR(10),
            legal_form_description VARCHAR(255),

            activity_start_date DATE,
            registration_date DATE,

            capitale_sociale BIGINT,

            email VARCHAR(255),
            pec VARCHAR(255),
            sdi VARCHAR(50),
            phone VARCHAR(50),

            registered_office TEXT,

            ateco_code VARCHAR(20),
            ateco_description TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # =========================================================
    # FINANCIAL OVERVIEW
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_financial_overview (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,
            financial_year INT NOT NULL,

            fatturato BIGINT,
            utile BIGINT,
            costo_personale BIGINT,
            numero_dipendenti INT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_financial_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE,

            CONSTRAINT unique_financial_year
                UNIQUE(company_id, financial_year)
        );
    """)

    # =========================================================
    # BALANCE SHEET
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_balance_sheet (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,
            financial_year INT NOT NULL,

            balance_date DATE,
            tipo_bilancio VARCHAR(10),
            atto_bilancio INT,

            ricavi_operativi BIGINT,
            ricavi_e_proventi BIGINT,
            totale_valore_produzione BIGINT,
            totale_costi_produzione BIGINT,

            costo_per_acquisti BIGINT,
            costo_per_servizi BIGINT,
            costo_per_godimento_beni_terzi BIGINT,
            costo_personale BIGINT,

            oneri_diversi_gestione BIGINT,

            ebitda BIGINT,
            ammortamenti_svalutazioni BIGINT,
            ebit BIGINT,

            proventi_oneri_finanziari BIGINT,

            risultato_prima_imposte BIGINT,
            imposte_reddito BIGINT,

            utile_perdita_esercizio BIGINT,
            flusso_di_cassa BIGINT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_balance_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE,

            CONSTRAINT unique_balance_year
                UNIQUE(company_id, financial_year)
        );
    """)

    # =========================================================
    # ASSETS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_assets (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,
            financial_year INT NOT NULL,

            immobilizzazioni_immateriali BIGINT,
            immobilizzazioni_materiali BIGINT,
            totale_immobilizzazioni BIGINT,

            totale_crediti BIGINT,
            crediti_entro_12_mesi BIGINT,

            totale_disponibilita_liquide BIGINT,
            totale_attivo_circolante BIGINT,

            ratei_risconti_attivi BIGINT,
            totale_attivo BIGINT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_assets_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE,

            CONSTRAINT unique_assets_year
                UNIQUE(company_id, financial_year)
        );
    """)

    # =========================================================
    # LIABILITIES
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_liabilities (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,
            financial_year INT NOT NULL,

            patrimonio_netto BIGINT,
            capitale_sociale BIGINT,
            altre_riserve BIGINT,

            utile_perdita_esercizio BIGINT,

            fondo_tfr BIGINT,

            totale_debiti BIGINT,
            debiti_entro_12_mesi BIGINT,
            debiti_oltre_12_mesi BIGINT,

            ratei_risconti_passivi BIGINT,
            totale_passivo BIGINT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_liabilities_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE,

            CONSTRAINT unique_liabilities_year
                UNIQUE(company_id, financial_year)
        );
    """)

    # =========================================================
    # INDICES
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_indices (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,
            financial_year INT NOT NULL,

            perc_variazione_ricavi NUMERIC(10,2),
            perc_variazione_valore_produzione NUMERIC(10,2),
            perc_variazione_attivo NUMERIC(10,2),
            perc_variazione_patrimonio_netto NUMERIC(10,2),

            perc_ros NUMERIC(10,2),
            perc_roi NUMERIC(10,2),
            perc_roe NUMERIC(10,2),

            indice_disponibilita NUMERIC(10,2),
            indice_liquidita_immediata NUMERIC(10,2),

            pfn BIGINT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_indices_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE,

            CONSTRAINT unique_indices_year
                UNIQUE(company_id, financial_year)
        );
    """)

    # =========================================================
    # CONTACTS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_contacts (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,

            contact_type VARCHAR(50),
            contact_value TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_contacts_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE
        );
    """)

    # =========================================================
    # PEOPLE
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_people (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,

            person_cf VARCHAR(50),

            first_name VARCHAR(100),
            last_name VARCHAR(100),

            full_name VARCHAR(255),

            role_code VARCHAR(20),
            role_name VARCHAR(255),

            category VARCHAR(50),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_people_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE
        );
    """)

    # =========================================================
    # SHAREHOLDERS
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_shareholders (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT NOT NULL,

            shareholder_cf VARCHAR(50),
            shareholder_name VARCHAR(255),

            ownership_percentage NUMERIC(10,2),

            nominal_value BIGINT,
            paid_value BIGINT,

            ownership_code VARCHAR(20),
            ownership_description VARCHAR(255),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_shareholders_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE
        );
    """)

    # =========================================================
    # RAW JSON BACKUP
    # =========================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS italy_company_raw_json (
            id BIGSERIAL PRIMARY KEY,

            company_id BIGINT,

            raw_json JSONB,

            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT fk_rawjson_company
                FOREIGN KEY(company_id)
                REFERENCES italy_companies(id)
                ON DELETE CASCADE
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("All Italy tables created successfully.")





def clear_all_tables():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        # get all tables
        cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public';
        """)

        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            return "No tables found"

        # disable FK checks
        cursor.execute("SET session_replication_role = 'replica';")

        # delete all data
        for table in tables:
            cursor.execute(f'TRUNCATE TABLE "{table}" CASCADE;')

        # enable FK checks back
        cursor.execute("SET session_replication_role = 'origin';")

        conn.commit()

        return f"Cleared {len(tables)} tables successfully"

    except Exception as e:
        conn.rollback()
        return f"Error: {str(e)}"

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print(clear_all_tables())
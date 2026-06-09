import os
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import json

from dynamoDB.italy_region_services import check_schedules_availability, save_company_schedules, get_company_schedules
from repository.respository_connection import get_connection
from services.region.italy.ReportAziende.api_integration import get_company_details_form_reportaziende


# =========================================================
# FUNCTION: CHECK IF COMPANY DATA EXISTS IN DATABASE
# =========================================================

def check_if_data_available_in_db(cid: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM italy_companies WHERE company_code = %s LIMIT 1",
            (cid,)
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()

# =========================================================
# FUNCTION 2: GET COMPANY BY ID (returns original structure)
# =========================================================

def get_company_full_data(company_code: str):
    conn = get_connection()

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # =========================================================
        # STEP 1: GET COMPANY
        # =========================================================
        cursor.execute("""
            SELECT *
            FROM italy_companies
            WHERE company_code = %s
            LIMIT 1
        """, (company_code,))

        company = cursor.fetchone()

        if not company:
            return {
                "success": False,
                "message": f"No company found for code: {company_code}"
            }

        company_id = company["id"]

        # =========================================================
        # STEP 2: GET ALL TABLES
        # =========================================================
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """)

        tables = [row["table_name"] for row in cursor.fetchall()]

        result = {
            "company": company,
            "related_data": {}
        }

        # =========================================================
        # STEP 3: FETCH RELATED DATA FROM ALL TABLES
        # =========================================================
        for table in tables:

            # Skip main company table
            if table == "italy_companies":
                continue

            try:
                # Get columns of table
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = %s
                """, (table,))

                columns = [col["column_name"] for col in cursor.fetchall()]

                # Check possible relation columns
                relation_column = None

                if "company_id" in columns:
                    relation_column = "company_id"

                elif "company_code" in columns:
                    relation_column = "company_code"

                # If relation exists, fetch data
                if relation_column:

                    if relation_column == "company_id":
                        query = f'''
                            SELECT *
                            FROM "{table}"
                            WHERE company_id = %s
                        '''
                        cursor.execute(query, (company_id,))

                    else:
                        query = f'''
                            SELECT *
                            FROM "{table}"
                            WHERE company_code = %s
                        '''
                        cursor.execute(query, (company_code,))

                    rows = cursor.fetchall()

                    result["related_data"][table] = rows

            except Exception as e:
                result["related_data"][table] = {
                    "error": str(e)
                }

        return {
            "success": True,
            "data": result
        }

    finally:
        cursor.close()
        conn.close()

# =========================================================
# FUNCTION 3: SAVE COMPANY DATA
# =========================================================

def save_italy_company(data: dict) -> int:
    """
    Takes the full API response dict and saves all records to DB.
    Returns the company_id (id in italy_companies).
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        schede = data.get("schede", {})
        ana = schede.get("ANA", {}).get("dati", {})
        forma = ana.get("forma_giuridica", {})
        ateco = ana.get("ateco", {})

        # ── MASTER COMPANY ──────────────────────────────
        cursor.execute("""
            INSERT INTO italy_companies (
                company_code, company_name,
                partita_iva, codice_fiscale,
                legal_form_class, legal_form_code, legal_form_description,
                activity_start_date, registration_date,
                capitale_sociale,
                email, pec, sdi, phone,
                registered_office,
                ateco_code, ateco_description
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (company_code) DO UPDATE SET
                company_name            = EXCLUDED.company_name,
                partita_iva             = EXCLUDED.partita_iva,
                legal_form_class        = EXCLUDED.legal_form_class,
                legal_form_code         = EXCLUDED.legal_form_code,
                legal_form_description  = EXCLUDED.legal_form_description,
                activity_start_date     = EXCLUDED.activity_start_date,
                registration_date       = EXCLUDED.registration_date,
                capitale_sociale        = EXCLUDED.capitale_sociale,
                email                   = EXCLUDED.email,
                pec                     = EXCLUDED.pec,
                sdi                     = EXCLUDED.sdi,
                phone                   = EXCLUDED.phone,
                registered_office       = EXCLUDED.registered_office,
                ateco_code              = EXCLUDED.ateco_code,
                ateco_description       = EXCLUDED.ateco_description,
                updated_at              = CURRENT_TIMESTAMP
            RETURNING id
        """, (
            ana.get("codice_fiscale"),
            ana.get("ragione_sociale"),
            ana.get("partita_iva"),
            ana.get("codice_fiscale"),
            forma.get("classe"),
            forma.get("codice"),
            forma.get("descrizione"),
            ana.get("inizio_attivita"),
            ana.get("data_iscrizione"),
            ana.get("capitale_sociale"),
            ana.get("email"),
            ana.get("pec"),
            ana.get("sdi"),
            ana.get("telefono"),
            ana.get("sede_legale"),
            ateco.get("codice"),
            ateco.get("descrizione"),
        ))

        company_id = cursor.fetchone()[0]

        # ── FINANCIAL OVERVIEW (scheda 05) ───────────────
        for year, row in schede.get("05", {}).get("dati", {}).items():
            cursor.execute("""
                INSERT INTO italy_company_financial_overview
                    (company_id, financial_year, fatturato, utile, costo_personale, numero_dipendenti)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, financial_year) DO UPDATE SET
                    fatturato        = EXCLUDED.fatturato,
                    utile            = EXCLUDED.utile,
                    costo_personale  = EXCLUDED.costo_personale,
                    numero_dipendenti = EXCLUDED.numero_dipendenti
            """, (
                company_id, int(year),
                row.get("fatturato"), row.get("utile"),
                row.get("costo_personale"), row.get("numero_dipendenti"),
            ))

        # ── BALANCE SHEET (scheda 10) ────────────────────
        for year, row in schede.get("10", {}).get("dati", {}).items():
            cursor.execute("""
                INSERT INTO italy_company_balance_sheet (
                    company_id, financial_year, balance_date, tipo_bilancio, atto_bilancio,
                    ricavi_operativi, ricavi_e_proventi, totale_valore_produzione, totale_costi_produzione,
                    costo_per_acquisti, costo_per_servizi, costo_per_godimento_beni_terzi, costo_personale,
                    oneri_diversi_gestione, ebitda, ammortamenti_svalutazioni, ebit,
                    proventi_oneri_finanziari, risultato_prima_imposte, imposte_reddito,
                    utile_perdita_esercizio, flusso_di_cassa
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )
                ON CONFLICT (company_id, financial_year) DO UPDATE SET
                    balance_date                    = EXCLUDED.balance_date,
                    ricavi_operativi                = EXCLUDED.ricavi_operativi,
                    ricavi_e_proventi               = EXCLUDED.ricavi_e_proventi,
                    totale_valore_produzione        = EXCLUDED.totale_valore_produzione,
                    totale_costi_produzione         = EXCLUDED.totale_costi_produzione,
                    costo_per_acquisti              = EXCLUDED.costo_per_acquisti,
                    costo_per_servizi               = EXCLUDED.costo_per_servizi,
                    costo_per_godimento_beni_terzi  = EXCLUDED.costo_per_godimento_beni_terzi,
                    costo_personale                 = EXCLUDED.costo_personale,
                    oneri_diversi_gestione          = EXCLUDED.oneri_diversi_gestione,
                    ebitda                          = EXCLUDED.ebitda,
                    ammortamenti_svalutazioni       = EXCLUDED.ammortamenti_svalutazioni,
                    ebit                            = EXCLUDED.ebit,
                    proventi_oneri_finanziari       = EXCLUDED.proventi_oneri_finanziari,
                    risultato_prima_imposte         = EXCLUDED.risultato_prima_imposte,
                    imposte_reddito                 = EXCLUDED.imposte_reddito,
                    utile_perdita_esercizio         = EXCLUDED.utile_perdita_esercizio,
                    flusso_di_cassa                 = EXCLUDED.flusso_di_cassa
            """, (
                company_id, int(year),
                row.get("data"), row.get("tipo_bilancio"), row.get("atto_bilancio"),
                row.get("RICAVI_OPERATIVI"), row.get("RICAVI_E_PROVENTI"),
                row.get("TOTALE_VALORE_DELLA_PRODUZIONE"), row.get("TOTALE_COSTI_DELLA_PRODUZIONE"),
                row.get("COSTO_PER_ACQUISTI"), row.get("COSTO_PER_SERVIZI"),
                row.get("COSTO_PER_GODIMENTO_DI_BENI_DI_TERZI"), row.get("COSTO_DEL_PERSONALE"),
                row.get("ONERI_DIVERSI_DI_GESTIONE"),
                row.get("MARGINE_OPERATIVO_LORDO_EBITDA"), row.get("AMMORTAMENTI_E_SVALUTAZIONI"),
                row.get("RISULTATO_OPERATIVO_EBIT"), row.get("PROVENTI_E_ONERI_FINANZIARI"),
                row.get("RISULTATO_PRIMA_DELLE_IMPOSTE"), row.get("IMPOSTE_SUL_REDDITO_ESERCIZIO"),
                row.get("UTILE_PERDITA_ESERCIZIO"), row.get("FLUSSO_DI_CASSA"),
            ))

        # ── ASSETS (scheda 20) ───────────────────────────
        for year, row in schede.get("20", {}).get("dati", {}).items():
            cursor.execute("""
                INSERT INTO italy_company_assets (
                    company_id, financial_year,
                    immobilizzazioni_immateriali, immobilizzazioni_materiali, totale_immobilizzazioni,
                    totale_crediti, crediti_entro_12_mesi,
                    totale_disponibilita_liquide, totale_attivo_circolante,
                    ratei_risconti_attivi, totale_attivo
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (company_id, financial_year) DO UPDATE SET
                    immobilizzazioni_immateriali  = EXCLUDED.immobilizzazioni_immateriali,
                    immobilizzazioni_materiali    = EXCLUDED.immobilizzazioni_materiali,
                    totale_immobilizzazioni       = EXCLUDED.totale_immobilizzazioni,
                    totale_crediti               = EXCLUDED.totale_crediti,
                    crediti_entro_12_mesi        = EXCLUDED.crediti_entro_12_mesi,
                    totale_disponibilita_liquide = EXCLUDED.totale_disponibilita_liquide,
                    totale_attivo_circolante     = EXCLUDED.totale_attivo_circolante,
                    ratei_risconti_attivi        = EXCLUDED.ratei_risconti_attivi,
                    totale_attivo               = EXCLUDED.totale_attivo
            """, (
                company_id, int(year),
                row.get("IMMOBILIZZAZIONI_IMMATERIALI"), row.get("IMMOBILIZZAZIONI_MATERIALI"),
                row.get("TOTALE_IMMOBILIZZAZIONI"), row.get("TOTALE_CREDITI"),
                row.get("CREDITI_ENTRO_12_MESI"), row.get("TOTALE_DISPONIBILITA_LIQUIDE"),
                row.get("TOTALE_ATTIVO_CIRCOLANTE"), row.get("RATEI_E_RISCONTI_ATTIVI"),
                row.get("TOTALE_ATTIVO"),
            ))

        # ── LIABILITIES (scheda 30) ──────────────────────
        for year, row in schede.get("30", {}).get("dati", {}).items():
            cursor.execute("""
                INSERT INTO italy_company_liabilities (
                    company_id, financial_year,
                    patrimonio_netto, capitale_sociale, altre_riserve, utile_perdita_esercizio,
                    fondo_tfr, totale_debiti, debiti_entro_12_mesi, debiti_oltre_12_mesi,
                    ratei_risconti_passivi, totale_passivo
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (company_id, financial_year) DO UPDATE SET
                    patrimonio_netto       = EXCLUDED.patrimonio_netto,
                    capitale_sociale       = EXCLUDED.capitale_sociale,
                    altre_riserve          = EXCLUDED.altre_riserve,
                    utile_perdita_esercizio = EXCLUDED.utile_perdita_esercizio,
                    fondo_tfr              = EXCLUDED.fondo_tfr,
                    totale_debiti          = EXCLUDED.totale_debiti,
                    debiti_entro_12_mesi   = EXCLUDED.debiti_entro_12_mesi,
                    debiti_oltre_12_mesi   = EXCLUDED.debiti_oltre_12_mesi,
                    ratei_risconti_passivi = EXCLUDED.ratei_risconti_passivi,
                    totale_passivo         = EXCLUDED.totale_passivo
            """, (
                company_id, int(year),
                row.get("patrimonio_netto"), row.get("capitale_sociale"),
                row.get("altre_riserve"), row.get("utile_perdita_esercizio"),
                row.get("fondo_tfr"), row.get("totale_debiti"),
                row.get("debiti_entro_12_mesi"), row.get("debiti_oltre_12_mesi"),
                row.get("ratei_risconti_passivi"), row.get("totale_passivo"),
            ))

        # ── INDICES (scheda 40) ──────────────────────────
        for year, row in schede.get("40", {}).get("dati", {}).items():
            cursor.execute("""
                INSERT INTO italy_company_indices (
                    company_id, financial_year,
                    perc_variazione_ricavi, perc_variazione_valore_produzione,
                    perc_variazione_attivo, perc_variazione_patrimonio_netto,
                    perc_ros, perc_roi, perc_roe,
                    indice_disponibilita, indice_liquidita_immediata, pfn
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (company_id, financial_year) DO UPDATE SET
                    perc_variazione_ricavi              = EXCLUDED.perc_variazione_ricavi,
                    perc_variazione_valore_produzione   = EXCLUDED.perc_variazione_valore_produzione,
                    perc_variazione_attivo              = EXCLUDED.perc_variazione_attivo,
                    perc_variazione_patrimonio_netto    = EXCLUDED.perc_variazione_patrimonio_netto,
                    perc_ros                            = EXCLUDED.perc_ros,
                    perc_roi                            = EXCLUDED.perc_roi,
                    perc_roe                            = EXCLUDED.perc_roe,
                    indice_disponibilita                = EXCLUDED.indice_disponibilita,
                    indice_liquidita_immediata          = EXCLUDED.indice_liquidita_immediata,
                    pfn                                 = EXCLUDED.pfn
            """, (
                company_id, int(year),
                row.get("perc_variazione_ricavi"), row.get("perc_variazione_valore_produzione"),
                row.get("perc_variazione_attivo"), row.get("perc_variazione_patrimonio_netto"),
                row.get("perc_ros"), row.get("perc_roi"), row.get("perc_roe"),
                row.get("indice_disponibilita"), row.get("indice_liquidita_immediata"),
                row.get("pfn"),
            ))

        # ── CONTACTS (scheda 85) ─────────────────────────
        contatti = schede.get("85", {}).get("dati", {}).get("contatti", {})

        cursor.execute("DELETE FROM italy_company_contacts WHERE company_id = %s", (company_id,))

        for phone in contatti.get("telefoni", []):
            cursor.execute("""
                INSERT INTO italy_company_contacts (company_id, contact_type, contact_value)
                VALUES (%s, 'telefono', %s)
            """, (company_id, phone))

        for cell in contatti.get("cellulari", []):
            cursor.execute("""
                INSERT INTO italy_company_contacts (company_id, contact_type, contact_value)
                VALUES (%s, 'cellulare', %s)
            """, (company_id, cell))

        for email in contatti.get("email", []):
            cursor.execute("""
                INSERT INTO italy_company_contacts (company_id, contact_type, contact_value)
                VALUES (%s, 'email', %s)
            """, (company_id, email))

        for pec in contatti.get("pec", []):
            cursor.execute("""
                INSERT INTO italy_company_contacts (company_id, contact_type, contact_value)
                VALUES (%s, 'pec', %s)
            """, (company_id, pec))

        for web in contatti.get("siti_web", []):
            cursor.execute("""
                INSERT INTO italy_company_contacts (company_id, contact_type, contact_value)
                VALUES (%s, 'sito_web', %s)
            """, (company_id, web))

        # ── PEOPLE: ceo_amministratori + esponenti ───────
        cursor.execute("DELETE FROM italy_company_people WHERE company_id = %s", (company_id,))

        for person in schede.get("85", {}).get("dati", {}).get("ceo_amministratori", []):
            cursor.execute("""
                INSERT INTO italy_company_people
                    (company_id, person_cf, first_name, last_name, full_name, role_code, role_name, category)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                company_id, person.get("cf"),
                person.get("nome"), person.get("cognome"), person.get("denominazione"),
                person.get("carica_code"), person.get("carica"), "ceo_amministratore",
            ))

        for person in schede.get("85", {}).get("dati", {}).get("esponenti", []):
            cursor.execute("""
                INSERT INTO italy_company_people
                    (company_id, person_cf, first_name, last_name, full_name, role_code, role_name, category)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                company_id, person.get("cf"),
                person.get("nome"), person.get("cognome"), person.get("denominazione"),
                person.get("carica_code"), person.get("carica"), "esponente",
            ))

        # ── SHAREHOLDERS ─────────────────────────────────
        cursor.execute("DELETE FROM italy_company_shareholders WHERE company_id = %s", (company_id,))

        for socio in schede.get("85", {}).get("dati", {}).get("soci", []):
            cursor.execute("""
                INSERT INTO italy_company_shareholders (
                    company_id, shareholder_cf, shareholder_name,
                    ownership_percentage, nominal_value, paid_value,
                    ownership_code, ownership_description
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                company_id, socio.get("cf"), socio.get("denominazione"),
                socio.get("quota_perc_cons"), socio.get("valore_nominale"), socio.get("valore_versato"),
                socio.get("codice_proprieta"), socio.get("descrizione_proprieta"),
            ))

        # ── RAW JSON ─────────────────────────────────────
        cursor.execute("""
            INSERT INTO italy_company_raw_json (company_id, raw_json)
            VALUES (%s, %s)
        """, (company_id, json.dumps(data)))

        conn.commit()
        print(f"✅ Company saved with id={company_id}")
        return company_id

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def get_company_code(cid: int):
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT company_code
            FROM italy_companies
            WHERE id = %s
            LIMIT 1
        """, (cid,))

        result = cursor.fetchone()

        return result[0] if result else None

    finally:
        cursor.close()
        conn.close()

# =========================================================
# FUNCTION 4: GET COMPANY DETAILS FROM REPORTAZIENDE AND SAVE IT IN DATABASE
# =========================================================

NON_PERSISTENT_SCHEDULES = {"85"}

def get_and_save_company(company_code: str, schedules: list[str]) -> dict:

    # Check availability
    availability = check_schedules_availability(
        company_code,
        schedules
    )

    missing = [
        item["schedule"]
        for item in availability
        if not item["is_data_available"]
    ]

    # Fetch only missing schedules
    api_data = None

    if missing:
        print(f"Fetching schedules from API: {missing}")

        api_data = get_company_details_form_reportaziende(
            company_code,
            missing
        )

        if api_data:
            save_company_schedules(
                api_data,
                missing
            )

    # Load DB data
    response = get_company_schedules(
        company_code,
        schedules
    )

    if not response.get("success"):
        return response

    # Inject live schedules (85 etc.) into response
    if api_data:
        schede = api_data.get("schede", {})

        for schedule in NON_PERSISTENT_SCHEDULES:

            if schedule not in schedules:
                continue

            raw = schede.get(schedule)

            if raw is not None:
                response["data"][schedule] = raw.get(
                    "dati",
                    raw
                )

    return response



def get_all_records_italy(page: int):
    """
    Fetch paginated records from italy_companies_master_list.
    page: 1-based page number
    """
    offset = (page - 1) * 100

    sql = """
        SELECT *
        FROM italy_companies_master_list
        ORDER BY id
        LIMIT 100 OFFSET %s
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (offset,))
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()

SORTABLE_COLUMNS = {
    "revenue": "ricavi_operativi_2024",
    "ebit": "ebit_2024",
    "employees": "numero_dipendenti_2024",
    "company_name": "denominazione",
    "city": "comune",
    "id": "id",
}

def column_search_italy(
    company_code: str = "",
    company_name: str = "",
    city: str = "",
    industry_code: str = "",
    revenue_min: Optional[float] = None,
    revenue_max: Optional[float] = None,
    ebit_min: Optional[float] = None,
    ebit_max: Optional[float] = None,
    employees_min: Optional[float] = None,
    employees_max: Optional[float] = None,
    sort_by: str = "id",
    sort_order: str = "asc",   # "asc" | "desc"
    main_industry: str = "",
    sub_industry: str = "",
    page: int = 1,
    limit: int = 100,
):
    params = []
    conditions = []

    # ── TEXT FILTERS ──────────────────────────────────────────────
    if company_code and company_code.strip():
        conditions.append("(codice_fiscale ILIKE %s OR partita_iva ILIKE %s)")
        like = f"%{company_code.strip()}%"
        params.extend([like, like])

    if company_name and company_name.strip():
        conditions.append("denominazione ILIKE %s")
        params.append(f"%{company_name.strip()}%")

    if city and city.strip():
        conditions.append("comune ILIKE %s")
        params.append(f"%{city.strip()}%")

    if industry_code and industry_code.strip():
        conditions.append("codice_ateco ILIKE %s")
        params.append(f"%{industry_code.strip()}%")

    # ── NUMERIC FILTERS ───────────────────────────────────────────
    if revenue_min is not None:
        conditions.append("ricavi_operativi_2024 >= %s")
        params.append(revenue_min)
    if revenue_max is not None:
        conditions.append("ricavi_operativi_2024 <= %s")
        params.append(revenue_max)
    if ebit_min is not None:
        conditions.append("ebit_2024 >= %s")
        params.append(ebit_min)
    if ebit_max is not None:
        conditions.append("ebit_2024 <= %s")
        params.append(ebit_max)
    if employees_min is not None:
        conditions.append("numero_dipendenti_2024 >= %s")
        params.append(employees_min)
    if employees_max is not None:
        conditions.append("numero_dipendenti_2024 <= %s")
        params.append(employees_max)

    if main_industry and main_industry.strip():
        conditions.append("main_industry ILIKE %s")
        params.append(f"%{main_industry.strip()}%")

    if sub_industry and sub_industry.strip():
        conditions.append("sub_industry ILIKE %s")
        params.append(f"%{sub_industry.strip()}%")

    # ── BUILD QUERY ───────────────────────────────────────────────
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Safe sort column (whitelist, never interpolate user input directly)
    order_col = SORTABLE_COLUMNS.get(sort_by, "id")
    order_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    # NULLS LAST so NULL revenues don't float to the top
    offset = (page - 1) * limit

    count_sql = f"SELECT COUNT(*) FROM italy_companies_master_list {where_clause}"

    data_sql = f"""
        SELECT *
        FROM italy_companies_master_list
        {where_clause}
        ORDER BY {order_col} {order_dir} NULLS LAST
        LIMIT %s OFFSET %s
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # total count (same filters, no pagination)
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]

            # paginated data
            cur.execute(data_sql, params + [limit, offset])
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            data = [dict(zip(columns, row)) for row in rows]

        return {"total": total, "page": page, "limit": limit, "data": data}
    finally:
        conn.close()
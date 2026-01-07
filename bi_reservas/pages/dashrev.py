import pandas as pd
import streamlit as st

# ======================
# CONFIGURAÇÃO DA PÁGINA
# ======================

st.set_page_config(
    page_title="Dash Revenue",
    layout="wide"
)

st.title("📈 Dash Revenue — Resultados")
st.caption("Apresentação executiva de resultados mensais")

# ======================
# FUNÇÕES DE CARGA
# ======================


@st.cache_data(ttl=3600)
def load_data():
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )

    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["google_sheets"]["spreadsheet_id"])

    # ---- Aba principal de reservas ----
    ws_res = sh.worksheet(st.secrets["google_sheets"]["sheet_name"])
    df_res = pd.DataFrame(ws_res.get_all_records())
    df_res.columns = df_res.columns.str.strip()

    # ---- Aba Histórico Unidades ----
    ws_hist = sh.worksheet("Histórico Unidades")
    df_hist = pd.DataFrame(ws_hist.get_all_records())
    df_hist.columns = df_hist.columns.str.strip().str.lower()

    return df_res, df_hist


df_res, df_hist = load_data()

# ======================
# NORMALIZAÇÃO — FUNÇÕES
# ======================


def parse_brl(series):
    return (
        series.astype(str)
        .str.strip()
        .str.replace("\u00a0", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^\d.-]", "", regex=True)
        .replace("", "0")
        .astype(float)
    )

# ======================
# NORMALIZAÇÃO — RESERVAS
# ======================


df_res["mes_dt"] = pd.to_datetime(df_res["mes"] + "-01")

df_res["valor_mes"] = parse_brl(df_res["valor_mes"])
df_res["limpeza_mes"] = parse_brl(df_res["limpeza_mes"])

df_res["noites_mes"] = (
    df_res["noites_mes"]
    .astype(str)
    .str.replace(",", ".")
    .astype(float)
    .astype(int)
)

# ======================
# NORMALIZAÇÃO — HISTÓRICO UNIDADES
# ======================

# padroniza nomes para bater com reservas
df_hist = df_hist.rename(
    columns={
        "unit_name": "unidade",
        "property_name": "propriedade",
        "adm 360": "adm_fee"
    }
)

df_hist["mes_dt"] = pd.to_datetime(df_hist["mês"] + "-01")

df_hist["cleaning_revenue"] = pd.to_numeric(
    df_hist["cleaning_revenue"],
    errors="coerce"
).fillna(0)

df_hist["adm_fee"] = pd.to_numeric(
    df_hist["adm_fee"],
    errors="coerce"
).fillna(0)

df_hist["price_less_comission"] = pd.to_numeric(
    df_hist["price_less_comission"],
    errors="coerce"
).fillna(0)

# ======================
# FILTRO DE MÊS (EXECUTIVO)
# ======================

meses = (
    df_res[["mes", "mes_dt"]]
    .drop_duplicates()
    .sort_values("mes_dt")["mes"]
    .tolist()
)

mes_sel = st.selectbox(
    "📅 Selecione o mês de análise",
    meses,
    index=len(meses) - 1
)

df_res_m = df_res[df_res["mes"] == mes_sel]
df_hist_m = df_hist[df_hist["mês"] == mes_sel]

if df_res_m.empty:
    st.warning("Sem dados de reservas para o mês selecionado.")
    st.stop()

# ======================
# CHECK VISUAL (TEMPORÁRIO)
# ======================

st.info(
    f"""
    **Bases carregadas com sucesso**
    - Reservas: {len(df_res_m)} linhas
    - Histórico Unidades: {len(df_hist_m)} linhas
    """
)

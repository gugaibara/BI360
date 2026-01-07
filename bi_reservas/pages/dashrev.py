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

CORES_CANAIS = {
    "Airbnb": "#FF00CC",
    "Booking.com": "#0217FF",
    "Direct": "#02812C",
    "Direct_Partner": "#00CC7E",
    "Site": "#FF0000",
    "Expedia": "#EEFF00"
}

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
df_hist.columns = (
    df_hist.columns
    .str.strip()
    .str.lower()
)

df_hist["cleaning_revenue"] = parse_brl(df_hist["cleaning_revenue"])
df_hist["adm_360"] = parse_brl(df_hist["adm_360"])
df_hist["price_less_comission"] = parse_brl(df_hist["price_less_comission"])
df_hist["plclc"] = parse_brl(df_hist["plclc"])

# ======================
# FILTRO DE MÊS (EXECUTIVO)
# ======================

meses = (
    df_res[["mes", "mes_dt"]]
    .drop_duplicates()
    .sort_values("mes_dt")["mes"]
    .tolist()
)

# ======================
# FILTROS EXECUTIVOS
# ======================

c1, c2 = st.columns([1, 3])

with c1:
    mes_sel = st.selectbox(
        "📅 Mês de análise",
        meses,
        index=len(meses) - 1
    )

with c2:
    partners = ["Todos"] + sorted(df_res["partner"].dropna().unique().tolist())

    partner_sel = st.selectbox(
        "🤝 Partner",
        partners
    )

# ---- aplica filtros ----
df_res_m = df_res[df_res["mes"] == mes_sel]
df_hist_m = df_hist[
    (df_hist["mês"] == mes_sel) &
    (df_hist["partnership"].notna())
]

if partner_sel != "Todos":
    df_res_m = df_res_m[df_res_m["partner"] == partner_sel]
    df_hist_m = df_hist_m[df_hist_m["partnership"] == partner_sel]
    st.caption(f"Resultados para o partner: **{partner_sel}**")

if df_res_m.empty:
    st.warning("Sem dados de reservas para o mês selecionado.")
    st.stop()

# ======================
# KPIs EXECUTIVOS — MÊS
# ======================

st.markdown("### 📌 Resultados do Mês")

# ---- Base Reservas ----
periodo = pd.Period(mes_sel, freq="M")
dias_mes = periodo.days_in_month

receita_total = df_res_m["valor_mes"].sum()
noites_ocupadas = df_res_m["noites_mes"].sum()

unidades = (
    df_res_m[["id_propriedade", "unidade"]]
    .drop_duplicates()
    .shape[0]
)

ocupacao = (
    (noites_ocupadas / (unidades * dias_mes)) * 100
    if unidades > 0 else 0
)

tarifa_media = (
    receita_total / noites_ocupadas
    if noites_ocupadas > 0 else 0
)

# ---- Base Histórico Unidades ----
cleaning_revenue = df_hist_m["cleaning_revenue"].sum()
taxa_adm = df_hist_m["adm_360"].sum()

# ---- Layout KPIs ----
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("💰 Receita Total", f"R$ {receita_total:,.2f}")
k2.metric("🏨 Ocupação", f"{ocupacao:.1f}%")
k3.metric("📊 Tarifa Média", f"R$ {tarifa_media:,.2f}")
k4.metric("🧹 Cleaning Revenue", f"R$ {cleaning_revenue:,.2f}")
k5.metric("🏷️ Taxa Adm", f"R$ {taxa_adm:,.2f}")

# ======================
# SHARE DE CANAL
# ======================

st.divider()
st.subheader("📊 Share de Canal")

canal_share = (
    df_res_m
    .groupby("canal", as_index=False)["valor_mes"]
    .sum()
)

total_receita = canal_share["valor_mes"].sum()

if total_receita == 0:
    st.info("Sem dados suficientes para calcular o share de canal.")
else:
    canal_share["share"] = canal_share["valor_mes"] / total_receita

    fig_share = px.pie(
        canal_share,
        names="canal",
        values="valor_mes",
        hole=0.45,
        title="Distribuição de Receita por Canal",
        color="canal",
        color_discrete_map=CORES_CANAIS
    )

    fig_share.update_traces(
        textinfo="label+percent",
        hovertemplate=(
            "Canal: %{label}<br>"
            "Receita: R$ %{value:,.2f}<br>"
            "Share: %{percent}"
        )
    )

    fig_share.update_layout(
        showlegend=True,
        margin=dict(t=60, b=20, l=20, r=20)
    )

    st.plotly_chart(fig_share, use_container_width=True)

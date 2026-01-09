import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go


def formatar_valor_exec(valor):
    if valor is None or pd.isna(valor):
        return "-"
    return f"R$ {valor:,.2f}"


def formatar_pct(valor, casas=1):
    if valor is None or pd.isna(valor):
        return "-"
    return f"{valor:.{casas}f}%"

# ======================
# CONFIGURAÇÃO DA PÁGINA
# ======================


st.set_page_config(
    page_title="Dash Revenue",
    layout="wide"
)

# ======================
# HEADER EXECUTIVO
# ======================

st.markdown(
    f"""
    <div style="
        background: linear-gradient(90deg, #2563eb, #1e40af);
        padding: 24px 28px;
        border-radius: 16px;
        color: white;
        margin-bottom: 20px;
    ">
        <h1 style="margin: 0; font-size: 34px;">📈 Dash Revenue</h1>
        <p style="margin: 6px 0 0 0; font-size: 16px; opacity: 0.9;">
            Resultados financeiros e operacionais — visão executiva
        </p>
    </div>
    """,
    unsafe_allow_html=True
)


CORES_CANAIS = {
    "Airbnb": "#FF00CC",
    "Booking.com": "#0217FF",
    "Direct": "#02812C",
    "Direct_Partner": "#00CC7E",
    "Site": "#FF0000",
    "Expedia": "#EEFF00"
}

CORES_NIVEIS = {
    "Nível 5": "#16a34a",   # verde forte (excelente)
    "Nível 4": "#4ade80",   # verde claro
    "Nível 3": "#facc15",   # amarelo
    "Nível 2": "#fb923c",   # laranja
    "Nível 1": "#ef4444",   # vermelho
    "Sem Meta": "#9ca3af"   # cinza
}

COR_SHARE = "#38bdf8"  # azul claro executivo

MAPA_NIVEL_NUM = {
    "Nível 1": 1,
    "Nível 2": 2,
    "Nível 3": 3,
    "Nível 4": 4,
    "Nível 5": 5
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
    df_res["mes_dt"] = pd.to_datetime(
        df_res["mes"].astype(str),
        errors="coerce"
    ).dt.to_period("M")

    # ---- Aba Histórico Unidades ----
    ws_hist = sh.worksheet("Histórico Unidades")
    values_hist = ws_hist.get_all_values()

    df_hist = pd.DataFrame(
        values_hist[1:],
        columns=values_hist[0]
    )

    df_hist.columns = df_hist.columns.str.strip().str.lower()

    # ---- Aba Base Níveis ----
    ws_meta = sh.worksheet("Base Níveis")
    df_meta = pd.DataFrame(ws_meta.get_all_records())
    df_meta.columns = df_meta.columns.str.strip().str.lower()

    return df_res, df_hist, df_meta


df_res, df_hist, df_meta = load_data()

# ======================
# NORMALIZAÇÃO DE PARTNER
# ======================

df_res["partner"] = df_res["partner"].astype(str).str.strip()
df_hist["partnership"] = df_hist["partnership"].astype(str).str.strip()
df_hist["plclcadm"] = df_hist["plclcadm"].fillna(0)

df_hist["mes_dt"] = pd.to_datetime(
    df_hist["mês"].astype(str),
    errors="coerce"
).dt.to_period("M")


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
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0.0)
    )

# ======================
# NORMALIZAÇÃO — BASE NÍVEIS
# ======================


df_meta["receita_esperada"] = parse_brl(df_meta["receita_esperada"])


def classificar_nivel(atingimento):
    if atingimento >= 1.15:
        return "Nível 5"
    elif atingimento >= 1:
        return "Nível 4"
    elif atingimento >= 0.85:
        return "Nível 3"
    elif atingimento >= 0.5:
        return "Nível 2"
    else:
        return "Nível 1"


# ======================
# NORMALIZAÇÃO — RESERVAS
# ======================

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
df_hist["plclcadm"] = parse_brl(df_hist["plclcadm"])

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
# SIDEBAR — FILTROS
# ======================

with st.sidebar:
    st.header("🔎 Filtros")

    mes_sel = st.selectbox(
        "📅 Mês de análise",
        meses,
        index=len(meses) - 1
    )

    partners = ["Todos"] + sorted(
        df_res["partner"].dropna().unique().tolist()
    )

    partner_sel = st.selectbox(
        "🤝 Partner",
        partners
    )

# ---- aplica filtros ----
periodo_sel = pd.Period(mes_sel, freq="M")

df_res_m = df_res[df_res["mes_dt"] == periodo_sel]

df_hist_m = df_hist[
    (df_hist["mes_dt"] == periodo_sel) &
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
# CONTEXTO DOS FILTROS
# ======================

st.markdown("### 🔎 Filtros Aplicados")

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        label="📅 Mês",
        value=mes_sel
    )

with c2:
    st.metric(
        label="🤝 Partner",
        value=partner_sel
    )

with c3:
    st.metric(
        label="🏘️ Unidades Ativas",
        value=df_res_m[["propriedade", "unidade"]].drop_duplicates().shape[0]
    )

st.divider()

# ======================
# KPIs COMPARATIVOS
# ======================


def calcular_kpis_mes(df, periodo):
    df_m = df[df["mes_dt"] == periodo]

    if df_m.empty:
        return None

    dias_mes_tmp = periodo.days_in_month

    receita = df_m["valor_mes"].sum()
    noites = df_m["noites_mes"].sum()

    unidades_tmp = (
        df_m[["id_propriedade", "unidade"]]
        .drop_duplicates()
        .shape[0]
    )

    ocupacao = (
        (noites / (unidades_tmp * dias_mes_tmp)) * 100
        if unidades_tmp > 0 else 0
    )

    tarifa_media = receita / noites if noites > 0 else 0

    return {
        "receita": receita,
        "ocupacao": ocupacao,
        "tarifa_media": tarifa_media
    }


def calcular_kpis_hist_mes(df_hist, periodo):
    df_m = df_hist[df_hist["mes_dt"] == periodo]

    if df_m.empty:
        return {"cleaning": None, "adm": None}

    return {
        "cleaning": df_m["cleaning_revenue"].sum(),
        "adm": df_m["adm_360"].sum()
    }


def calcular_base_niveis(df_hist, df_meta, periodo, partner_sel):
    """
    Retorna base por unidade com:
    - realizado_plclcadm
    - receita_esperada
    - atingimento
    - nivel (texto)
    - nivel_num (1 a 5)
    """

    # --- normaliza período ---
    if isinstance(periodo, pd.Period):
        periodo_str = periodo.strftime("%Y-%m")
    else:
        periodo_str = str(periodo)

    # --- filtra histórico ---
    df_m = df_hist[df_hist["mes_dt"] ==
                   pd.Period(periodo_str, freq="M")].copy()

    if partner_sel != "Todos":
        df_m = df_m[df_m["partnership"] == partner_sel]

    if df_m.empty:
        return pd.DataFrame()

    # --- soma PLCLCADM por unidade ---
    base = (
        df_m
        .groupby(["propriedade", "unidade"], as_index=False)
        .agg(realizado_plclcadm=("plclcadm", "sum"))
    )

    # --- merge com metas ---
    base = base.merge(
        df_meta,
        on=["propriedade", "unidade"],
        how="left"
    )

    # --- garante numérico ---
    base["realizado_plclcadm"] = pd.to_numeric(
        base["realizado_plclcadm"], errors="coerce"
    )

    base["receita_esperada"] = pd.to_numeric(
        base["receita_esperada"], errors="coerce"
    )

    # --- calcula atingimento ---
    base["atingimento"] = None
    mask = base["receita_esperada"] > 0

    base.loc[mask, "atingimento"] = (
        base.loc[mask, "realizado_plclcadm"] /
        base.loc[mask, "receita_esperada"]
    )

    # --- classifica nível ---
    base["nivel"] = "Sem Meta"
    base.loc[mask, "nivel"] = (
        base.loc[mask, "atingimento"]
        .apply(classificar_nivel)
    )

    base["nivel_num"] = base["nivel"].map(MAPA_NIVEL_NUM)

    return base


# ======================
# BASE PARA COMPARATIVOS (RESERVAS + HISTÓRICO)
# ======================


df_res_comp = df_res.copy()
df_hist_comp = df_hist.copy()

if partner_sel != "Todos":
    df_res_comp = df_res_comp[df_res_comp["partner"] == partner_sel]
    df_hist_comp = df_hist_comp[df_hist_comp["partnership"] == partner_sel]


# ======================
# PERÍODOS
# ======================

periodo = pd.Period(mes_sel, freq="M")

periodo_m1 = periodo - 1
periodo_yoy = periodo - 12

# ======================
# NÍVEL MÉDIO (ATUAL / M1 / YOY)
# ======================

base_niveis_atual = calcular_base_niveis(
    df_hist_comp, df_meta, periodo, partner_sel
)

metricas_nivel_atual = {
    "atingimento_medio": (
        base_niveis_atual["atingimento"].mean()
        if not base_niveis_atual.empty else None
    ),
    "nivel_medio": (
        base_niveis_atual["nivel_num"].mean()
        if not base_niveis_atual.empty else None
    )
}

base_niveis_m1 = calcular_base_niveis(
    df_hist_comp, df_meta, periodo_m1, partner_sel
)

metricas_nivel_m1 = {
    "atingimento_medio": (
        base_niveis_m1["atingimento"].mean()
        if not base_niveis_m1.empty else None
    ),
    "nivel_medio": (
        base_niveis_m1["nivel_num"].mean()
        if not base_niveis_m1.empty else None
    )
}

base_niveis_yoy = calcular_base_niveis(
    df_hist_comp, df_meta, periodo_yoy, partner_sel
)

metricas_nivel_yoy = {
    "atingimento_medio": (
        base_niveis_yoy["atingimento"].mean()
        if not base_niveis_yoy.empty else None
    ),
    "nivel_medio": (
        base_niveis_yoy["nivel_num"].mean()
        if not base_niveis_yoy.empty else None
    )
}

# ======================
# KPIs DE RESERVAS
# ======================

kpis_atual = calcular_kpis_mes(df_res_comp, periodo)
kpis_m1 = calcular_kpis_mes(df_res_comp, periodo_m1)
kpis_yoy = calcular_kpis_mes(df_res_comp, periodo_yoy)

if kpis_atual is None:
    st.warning("Sem dados para os filtros selecionados.")
    st.stop()

receita_total = kpis_atual["receita"]
ocupacao = kpis_atual["ocupacao"]
tarifa_media = kpis_atual["tarifa_media"]


# ======================
# KPIs HISTÓRICOS (CLEANING / ADM)
# ======================

kpis_hist_atual = calcular_kpis_hist_mes(df_hist_comp, periodo)
kpis_hist_m1 = calcular_kpis_hist_mes(df_hist_comp, periodo_m1)
kpis_hist_yoy = calcular_kpis_hist_mes(df_hist_comp, periodo_yoy)

cleaning_atual = kpis_hist_atual.get("cleaning") if kpis_hist_atual else None
cleaning_m1 = kpis_hist_m1.get("cleaning") if kpis_hist_m1 else None

adm_atual = kpis_hist_atual.get("adm") if kpis_hist_atual else None
adm_m1 = kpis_hist_m1.get("adm") if kpis_hist_m1 else None

# ======================
# FUNÇÃO DE VARIAÇÃO %
# ======================


def variacao_pct(atual, anterior):
    if (
        anterior is None or
        anterior == 0 or
        atual is None or
        pd.isna(atual) or
        pd.isna(anterior)
    ):
        return None
    return ((atual / anterior) - 1) * 100


# ---- Base Histórico Unidades ----
cleaning_revenue = df_hist_m["cleaning_revenue"].sum()
taxa_adm = df_hist_m["adm_360"].sum()

# ---- Layout KPIs ----
st.divider()
st.subheader("📊 Resumo Executivo do Mês")
st.caption(
    "Principais indicadores financeiros, operacionais e de performance "
    "para o período selecionado."
)

# ======================
# LINHA 1 — KPIs PRINCIPAIS
# ======================
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric(
        "Receita Total",
        formatar_valor_exec(receita_total)
    )

with k2:
    st.metric(
        "Ocupação",
        formatar_pct(ocupacao)
    )

with k3:
    st.metric(
        "Tarifa Média",
        formatar_valor_exec(tarifa_media)
    )

with k4:
    st.metric(
        "Nível Médio",
        f"{metricas_nivel_atual['nivel_medio']:.2f}"
        if metricas_nivel_atual["nivel_medio"] is not None else "-"
    )

# ======================
# LINHA 2 — KPIs FINANCEIROS
# ======================
k5, k6, k7, k8 = st.columns(4)

with k5:
    st.metric(
        "Cleaning Revenue",
        formatar_valor_exec(kpis_hist_atual["cleaning"])
        if kpis_hist_atual else "-"
    )

with k6:
    st.metric(
        "Taxa Adm",
        formatar_valor_exec(kpis_hist_atual["adm"])
        if kpis_hist_atual else "-"
    )

with k7:
    st.metric(
        "Unidades Analisadas",
        f"{df_res_m[['propriedade', 'unidade']].drop_duplicates().shape[0]}"
    )

with k8:
    st.metric(
        "Atingimento Médio",
        formatar_pct(metricas_nivel_atual["atingimento_medio"] * 100)
        if metricas_nivel_atual["atingimento_medio"] is not None else "-"
    )

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
        hole=0.4,
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

    st.plotly_chart(fig_share, use_container_width=True)

# ======================
# TABELA — SHARE DE CANAL
# ======================

if total_receita > 0:
    st.markdown("#### 📋 Receita por Canal")

    tabela_share = canal_share.copy()

    tabela_share["Receita (R$)"] = tabela_share["valor_mes"]
    tabela_share["Share (%)"] = tabela_share["share"] * 100

    tabela_share = (
        tabela_share[["canal", "Receita (R$)", "Share (%)"]]
        .sort_values("Receita (R$)", ascending=False)
        .reset_index(drop=True)
    )

    st.dataframe(
        tabela_share.style.format({
            "Receita (R$)": "R$ {:,.2f}",
            "Share (%)": "{:.1f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

# ======================
# DISTRIBUIÇÃO DE NÍVEIS
# ======================

nivel_base = base_niveis_atual.copy()

dist_niveis = (
    nivel_base
    .groupby("nivel", as_index=False)
    .agg(
        unidades=("unidade", "nunique"),
        atingimento_medio=("atingimento", "mean")
    )
)

total_unidades = dist_niveis["unidades"].sum()

if total_unidades > 0:
    dist_niveis["share"] = dist_niveis["unidades"] / total_unidades
else:
    dist_niveis["share"] = 0

ordem_niveis = [
    "Nível 5",
    "Nível 4",
    "Nível 3",
    "Nível 2",
    "Nível 1",
    "Sem Meta"
]

dist_niveis["nivel"] = pd.Categorical(
    dist_niveis["nivel"],
    categories=ordem_niveis,
    ordered=True
)

dist_niveis = dist_niveis.sort_values("nivel")

# ======================
# GRÁFICO COMBO DOS NÍVEIS
# ======================

st.divider()
st.subheader("🎯 Distribuição de Níveis — Quantidade e Share")
st.caption(f"Total de unidades analisadas: **{total_unidades}**")
fig = go.Figure()

# ---- Barras: quantidade de unidades ----
fig.add_trace(
    go.Bar(
        x=dist_niveis["nivel"],
        y=dist_niveis["unidades"],
        name="Nº de Unidades",
        marker_color=[CORES_NIVEIS[n] for n in dist_niveis["nivel"]],
        text=dist_niveis["unidades"],
        textposition="outside",
        opacity=0.9
    )
)

# ---- Linha: share (%) ----
fig.add_trace(
    go.Scatter(
        x=dist_niveis["nivel"],
        y=dist_niveis["share"] * 100,
        name="Share (%)",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color=COR_SHARE, width=3),
        marker=dict(size=8),
        hovertemplate="Share: %{y:.1f}%"
    )
)

max_share = (
    dist_niveis["share"].max() * 100
    if not dist_niveis.empty else 100
)

fig.update_layout(
    yaxis=dict(
        title="Nº de Unidades",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)"
    ),
    yaxis2=dict(
        title="Share (%)",
        overlaying="y",
        side="right",
        range=[0, max_share * 1.2],
        showgrid=False
    ),
    legend=dict(
        orientation="h",
        y=1.15,
        x=0.01
    ),
    bargap=0.25,
    margin=dict(t=80, b=40, l=40, r=40)
)

st.plotly_chart(fig, use_container_width=True)

# ======================
# TABELA — DISTRIBUIÇÃO DE NÍVEIS
# ======================

tabela_niveis = dist_niveis.copy()

tabela_niveis["Share (%)"] = tabela_niveis["share"] * 100
tabela_niveis["Atingimento Médio (%)"] = tabela_niveis["atingimento_medio"] * 100

tabela_niveis = tabela_niveis[
    ["nivel", "unidades", "Share (%)", "Atingimento Médio (%)"]
]

tabela_niveis = tabela_niveis.rename(
    columns={
        "nivel": "Nível",
        "unidades": "Nº de Unidades"
    }
)

st.dataframe(
    tabela_niveis.style.format({
        "Share (%)": "{:.1f}%",
        "Atingimento Médio (%)": "{:.1f}%"
    }),
    use_container_width=True,
    hide_index=True
)

# ======================
# COMPARATIVOS TEMPORAIS
# ======================

cards = []

# ======================
# VARIAÇÕES — NÍVEIS
# ======================

# MoM
var_ating_medio_m1 = (
    (metricas_nivel_atual["atingimento_medio"] -
     metricas_nivel_m1["atingimento_medio"]) * 100
    if (
        metricas_nivel_atual["atingimento_medio"] is not None and
        metricas_nivel_m1["atingimento_medio"] is not None
    ) else None
)

var_nivel_medio_m1 = (
    metricas_nivel_atual["nivel_medio"] -
    metricas_nivel_m1["nivel_medio"]
    if metricas_nivel_m1["nivel_medio"] is not None else None
)

# YoY
var_ating_medio_yoy = (
    (metricas_nivel_atual["atingimento_medio"] -
     metricas_nivel_yoy["atingimento_medio"]) * 100
    if (
        metricas_nivel_atual["atingimento_medio"] is not None and
        metricas_nivel_yoy["atingimento_medio"] is not None
    ) else None
)

var_nivel_medio_yoy = (
    metricas_nivel_atual["nivel_medio"] -
    metricas_nivel_yoy["nivel_medio"]
    if (
        metricas_nivel_atual["nivel_medio"] is not None and
        metricas_nivel_yoy["nivel_medio"] is not None
    ) else None
)

# ======================
# MOM — DETALHADO
# ======================

if kpis_m1:
    cards.append({
        "Comparação": "MoM",

        "Receita Atual": kpis_atual["receita"],
        "Receita M-1": kpis_m1["receita"],
        "Δ Receita": kpis_atual["receita"] - kpis_m1["receita"],

        "Ocupação Atual": kpis_atual["ocupacao"],
        "Ocupação M-1": kpis_m1["ocupacao"],
        "Δ Ocupação (pp)": kpis_atual["ocupacao"] - kpis_m1["ocupacao"],

        "Tarifa Atual": kpis_atual["tarifa_media"],
        "Tarifa M-1": kpis_m1["tarifa_media"],
        "Δ Tarifa": kpis_atual["tarifa_media"] - kpis_m1["tarifa_media"],

        "Cleaning Atual": cleaning_atual,
        "Cleaning M-1": cleaning_m1,
        "Δ Cleaning": (
            cleaning_atual - cleaning_m1
            if cleaning_atual is not None and cleaning_m1 is not None else None
        ),

        "Adm Atual": adm_atual,
        "Adm M-1": adm_m1,
        "Δ Adm": (
            adm_atual - adm_m1
            if adm_atual is not None and adm_m1 is not None else None
        ),

        "Atingimento Médio Atual (%)": (
            metricas_nivel_atual["atingimento_medio"] * 100
            if metricas_nivel_atual["atingimento_medio"] is not None else None
        ),
        "Atingimento Médio M-1 (%)": (
            metricas_nivel_m1["atingimento_medio"] * 100
            if metricas_nivel_m1["atingimento_medio"] is not None else None
        ),
        "Δ Atingimento Médio (pp)": var_ating_medio_m1,

        "Nível Médio Atual": metricas_nivel_atual["nivel_medio"],
        "Nível Médio M-1": metricas_nivel_m1["nivel_medio"],
        "Δ Nível Médio": var_nivel_medio_m1
    })

# ======================
# YOY — SINTÉTICO (PADRONIZADO)
# ======================

if kpis_yoy:
    cards.append({
        "Comparação": "YoY",

        "Receita (%)": variacao_pct(kpis_atual["receita"], kpis_yoy["receita"]),
        "Ocupação (pp)": kpis_atual["ocupacao"] - kpis_yoy["ocupacao"],
        "Tarifa Média (%)": variacao_pct(
            kpis_atual["tarifa_media"], kpis_yoy["tarifa_media"]
        ),
        "Cleaning Revenue (%)": (
            variacao_pct(
                kpis_hist_atual["cleaning"],
                kpis_hist_yoy["cleaning"]
            ) if kpis_hist_yoy else None
        ),
        "Taxa Adm (%)": (
            variacao_pct(
                kpis_hist_atual["adm"],
                kpis_hist_yoy["adm"]
            ) if kpis_hist_yoy else None
        ),
        "Atingimento Médio (pp)": var_ating_medio_yoy,
        "Nível Médio (Δ)": var_nivel_medio_yoy
    })

df_comp = pd.DataFrame(cards)

# ======================
# HISTÓRICO — ÚLTIMOS 3 MESES
# ======================

st.divider()
st.subheader("📊 Evolução Recente (Últimos 3 Meses)")
st.caption("Valores absolutos por mês e variação em relação ao mês anterior")

periodos_3m = [periodo - 2, periodo - 1, periodo]
labels_3m = [p.strftime("%b/%y") for p in periodos_3m]

# -------- Receita --------
receita_3m = [
    df_res_comp.loc[df_res_comp["mes_dt"] == p, "valor_mes"].sum()
    for p in periodos_3m
]

# -------- Ocupação --------
ocupacao_3m = []
tarifa_3m = []

for p in periodos_3m:
    k = calcular_kpis_mes(df_res_comp, p)
    ocupacao_3m.append(k["ocupacao"] if k else 0)
    tarifa_3m.append(k["tarifa_media"] if k else 0)

# -------- Cleaning / Adm --------
cleaning_3m = []
adm_3m = []

for p in periodos_3m:
    k = calcular_kpis_hist_mes(df_hist_comp, p)
    cleaning_3m.append(k["cleaning"] if k and k["cleaning"] else 0)
    adm_3m.append(k["adm"] if k and k["adm"] else 0)

# -------- Atingimento / Nível (USANDO A MESMA FUNÇÃO) --------
ating_3m = []
nivel_3m = []

for p in periodos_3m:
    base_tmp = calcular_base_niveis(df_hist_comp, df_meta, p, partner_sel)

    ating_3m.append(
        base_tmp["atingimento"].mean() * 100
        if not base_tmp.empty else 0
    )

    nivel_3m.append(
        base_tmp["nivel_num"].mean()
        if not base_tmp.empty else 0
    )


def grafico_historico_3m(titulo, valores, labels, nome_barra, unidade="", cor="#2563eb"):

    delta = None
    if len(valores) >= 2 and valores[-2] is not None:
        delta = valores[-1] - valores[-2]

    texto_delta = (
        f"Δ último mês: {delta:+,.2f}{unidade}"
        if isinstance(delta, (int, float))
        else "Δ último mês: -"
    )

    fig = go.Figure()
    fig.add_bar(
        x=labels,
        y=valores,
        marker_color=cor,
        text=[
            f"{v:,.2f}{unidade}" if isinstance(v, (int, float)) else "-"
            for v in valores
        ],
        textposition="outside"
    )

    fig.update_layout(
        title=f"{titulo}<br><sup>{texto_delta}</sup>",
        yaxis_title=nome_barra,
        margin=dict(t=90, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)


# -------- GRID --------


c1, c2, c3 = st.columns(3)
with c1:
    grafico_historico_3m(
        titulo="Receita",
        valores=receita_3m,
        labels=labels_3m,
        nome_barra="Receita (R$)"
    )

with c2:
    grafico_historico_3m(
        titulo="Ocupação",
        valores=ocupacao_3m,
        labels=labels_3m,
        nome_barra="Ocupação (%)",
        unidade="%",
        cor="#f97316"
    )

with c3:
    grafico_historico_3m(
        titulo="Tarifa Média",
        valores=tarifa_3m,
        labels=labels_3m,
        nome_barra="Tarifa Média (R$)"
    )


c4, c5 = st.columns(2)
with c4:
    grafico_historico_3m(
        titulo="Cleaning Revenue",
        valores=cleaning_3m,
        labels=labels_3m,
        nome_barra="Cleaning (R$)",
        cor="#dc2626"
    )

with c5:
    grafico_historico_3m(
        titulo="Taxa Adm",
        valores=adm_3m,
        labels=labels_3m,
        nome_barra="Taxa Adm (R$)",
        cor="#dc2626"
    )


c6, c7 = st.columns(2)
with c6:
    grafico_historico_3m(
        titulo="Atingimento Médio",
        valores=ating_3m,
        labels=labels_3m,
        nome_barra="Atingimento (%)",
        unidade="%",
        cor="#7c3aed"
    )

with c7:
    grafico_historico_3m(
        titulo="Nível Médio",
        valores=nivel_3m,
        labels=labels_3m,
        nome_barra="Nível Médio",
        cor="#7c3aed"
    )

# ======================
# TABELA FINAL (SOB DEMANDA)
# ======================

st.divider()

with st.expander("📋 Ver tabela completa de comparativos temporais"):
    if df_comp.empty:
        st.info("Não há dados suficientes para comparativos temporais.")
    else:
        st.dataframe(
            df_comp.style.format({
                "Receita Atual": "R$ {:,.0f}",
                "Receita M-1": "R$ {:,.0f}",
                "Δ Receita": "{:+,.0f}",

                "Ocupação Atual": "{:.1f}%",
                "Ocupação M-1": "{:.1f}%",

                "Tarifa Atual": "R$ {:,.2f}",
                "Tarifa M-1": "R$ {:,.2f}",

                "Cleaning Atual": "R$ {:,.0f}",
                "Cleaning M-1": "R$ {:,.0f}",

                "Adm Atual": "R$ {:,.0f}",
                "Adm M-1": "R$ {:,.0f}",

                "Atingimento Médio Atual (%)": "{:.1f}%",
                "Atingimento Médio M-1 (%)": "{:.1f}%",

                "Nível Médio Atual": "{:.2f}",
                "Nível Médio M-1": "{:.2f}",
            }),
            use_container_width=True,
            hide_index=True
        )

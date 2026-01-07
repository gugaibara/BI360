import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

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
    df_hist = pd.DataFrame(ws_hist.get_all_records())
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
# KPIs COMPARATIVOS
# ======================

st.markdown("### 📌 Resultados do Mês")


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


def calcular_metricas_nivel(df_res, df_meta, periodo, partner_sel):
    # filtra reservas do mês
    df_m = df_res[df_res["mes_dt"] == periodo].copy()

    if partner_sel != "Todos":
        df_m = df_m[df_m["partner"] == partner_sel]

    if df_m.empty:
        return {
            "atingimento_medio": None,
            "nivel_medio": None
        }

    # receita de diárias por unidade
    diarias_unidade = (
        df_m
        .groupby(["propriedade", "unidade"], as_index=False)
        .agg(
            valor_mes=("valor_mes", "sum"),
            limpeza_mes=("limpeza_mes", "sum")
        )
    )

    diarias_unidade["receita_diarias"] = (
        diarias_unidade["valor_mes"] -
        diarias_unidade["limpeza_mes"]
    )

    # merge com metas
    nivel_base = diarias_unidade.merge(
        df_meta,
        on=["propriedade", "unidade"],
        how="left"
    )

    # calcula atingimento
    nivel_base["atingimento"] = None
    mask = nivel_base["receita_esperada"] > 0

    nivel_base.loc[mask, "atingimento"] = (
        nivel_base.loc[mask, "receita_diarias"] /
        nivel_base.loc[mask, "receita_esperada"]
    )

    # classifica nível
    nivel_base.loc[mask, "nivel"] = (
        nivel_base.loc[mask, "atingimento"]
        .apply(classificar_nivel)
    )

    # converte nível para número
    nivel_base["nivel_num"] = nivel_base["nivel"].map(MAPA_NIVEL_NUM)

    return {
        "atingimento_medio": nivel_base.loc[mask, "atingimento"].mean(),
        "nivel_medio": nivel_base.loc[mask, "nivel_num"].mean()
    }


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

metricas_nivel_atual = calcular_metricas_nivel(
    df_res_comp, df_meta, periodo, partner_sel
)

metricas_nivel_m1 = calcular_metricas_nivel(
    df_res_comp, df_meta, periodo_m1, partner_sel
)

metricas_nivel_yoy = calcular_metricas_nivel(
    df_res_comp, df_meta, periodo_yoy, partner_sel
)

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

# ======================
# FUNÇÃO DE VARIAÇÃO %
# ======================


def variacao_pct(atual, anterior):
    if (
        atual is None or
        anterior is None or
        atual == 0 or
        anterior == 0 or
        pd.isna(atual) or
        pd.isna(anterior)
    ):
        return None

    return ((atual / anterior) - 1) * 100


# ---- Base Histórico Unidades ----
cleaning_revenue = df_hist_m["cleaning_revenue"].sum()
taxa_adm = df_hist_m["adm_360"].sum()

# ---- Layout KPIs ----
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)

k1.metric("💰 Receita Total", f"R$ {receita_total:,.2f}")
k2.metric("🏨 Ocupação", f"{ocupacao:.1f}%")
k3.metric("📊 Tarifa Média", f"R$ {tarifa_media:,.2f}")
k4.metric(
    "🧹 Cleaning Revenue",
    f"R$ {cleaning_revenue:,.2f}" if cleaning_revenue > 0 else "—"
)
k5.metric(
    "🏷️ Taxa Adm",
    f"R$ {taxa_adm:,.2f}" if taxa_adm > 0 else "—"
)
# 🎯 Atingimento Médio
k6.metric(
    "🎯 Atingimento Médio",
    f"{metricas_nivel_atual['atingimento_medio']*100:.1f}%"
    if metricas_nivel_atual["atingimento_medio"] is not None else "—"
)

# 🧭 Nível Médio
k7.metric(
    "🧭 Nível Médio",
    f"{metricas_nivel_atual['nivel_medio']:.2f}"
    if metricas_nivel_atual["nivel_medio"] is not None else "—"
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

# receita de diárias por unidade no mês
diarias_unidade = (
    df_res_m
    .groupby(["propriedade", "unidade"], as_index=False)
    .agg({
        "valor_mes": "sum",
        "limpeza_mes": "sum"
    })
)

diarias_unidade["receita_diarias"] = (
    diarias_unidade["valor_mes"] -
    diarias_unidade["limpeza_mes"]
)

nivel_base = diarias_unidade.merge(
    df_meta,
    on=["propriedade", "unidade"],
    how="left"
)

nivel_base["atingimento"] = None

mask = nivel_base["receita_esperada"] > 0

nivel_base.loc[mask, "atingimento"] = (
    nivel_base.loc[mask, "receita_diarias"] /
    nivel_base.loc[mask, "receita_esperada"]
)

nivel_base["nivel"] = "Sem Meta"

mask_meta = nivel_base["receita_esperada"] > 0

nivel_base.loc[mask_meta, "nivel"] = (
    nivel_base.loc[mask_meta, "atingimento"]
    .apply(classificar_nivel)
)

# ======================
# AGREGAÇÃO POR NÍVEL
# ======================

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

st.divider()
st.subheader("📈 Comparativos Temporais")

cards = []

# ======================
# VARIAÇÃO DO NÍVEL MÉDIO
# ======================

# Atingimento médio (pp)
var_ating_medio_m1 = (
    (metricas_nivel_atual["atingimento_medio"] -
     metricas_nivel_m1["atingimento_medio"]) * 100
    if (
        metricas_nivel_atual["atingimento_medio"] is not None and
        metricas_nivel_m1["atingimento_medio"] is not None
    ) else None
)

# Nível médio (diferença absoluta)
var_nivel_medio_m1 = (
    metricas_nivel_atual["nivel_medio"] -
    metricas_nivel_m1["nivel_medio"]
    if metricas_nivel_m1["nivel_medio"] is not None else None
)


# ======================
# MOM
# ======================

if kpis_m1:
    cards.append({
        "Comparação": "MoM",

        # Receita
        "Receita Atual": kpis_atual["receita"],
        "Receita M-1": kpis_m1["receita"],
        "Δ Receita": kpis_atual["receita"] - kpis_m1["receita"],
        "Receita (%)": variacao_pct(
            kpis_atual["receita"], kpis_m1["receita"]
        ),

        # Ocupação
        "Ocupação Atual": kpis_atual["ocupacao"],
        "Ocupação M-1": kpis_m1["ocupacao"],
        "Δ Ocupação (pp)": (
            kpis_atual["ocupacao"] - kpis_m1["ocupacao"]
        ),

        # Tarifa
        "Tarifa Atual": kpis_atual["tarifa_media"],
        "Tarifa M-1": kpis_m1["tarifa_media"],
        "Δ Tarifa": kpis_atual["tarifa_media"] - kpis_m1["tarifa_media"],

        # Cleaning
        "Cleaning Atual": (
            kpis_hist_atual["cleaning"]
            if kpis_hist_atual else None
        ),
        "Cleaning M-1": (
            kpis_hist_m1["cleaning"]
            if kpis_hist_m1 else None
        ),
        "Δ Cleaning": (
            kpis_hist_atual["cleaning"] - kpis_hist_m1["cleaning"]
            if (
                kpis_hist_atual["cleaning"] is not None and
                kpis_hist_m1 is not None and
                kpis_hist_m1["cleaning"] is not None
            ) else None
        ),
        # Adm
        "Adm Atual": (
            kpis_hist_atual["adm"]
            if kpis_hist_atual else None
        ),
        "Adm M-1": (
            kpis_hist_m1["adm"]
            if kpis_hist_m1 else None
        ),
        "Δ Adm": (
            kpis_hist_atual["adm"] - kpis_hist_m1["adm"]
            if (
                kpis_hist_atual["adm"] is not None and
                kpis_hist_m1 is not None and
                kpis_hist_m1["adm"] is not None
            ) else None
        ),

        # Níveis
        "Atingimento Médio Atual (%)": (
            metricas_nivel_atual["atingimento_medio"] * 100
            if metricas_nivel_atual["atingimento_medio"] else None
        ),
        "Atingimento Médio M-1 (%)": (
            metricas_nivel_m1["atingimento_medio"] * 100
            if metricas_nivel_m1["atingimento_medio"] else None
        ),
        "Δ Atingimento Médio (pp)": (
            (metricas_nivel_atual["atingimento_medio"] -
             metricas_nivel_m1["atingimento_medio"]) * 100
            if metricas_nivel_m1["atingimento_medio"] else None
        ),

        "Nível Médio Atual": metricas_nivel_atual["nivel_medio"],
        "Nível Médio M-1": metricas_nivel_m1["nivel_medio"],
        "Δ Nível Médio": (
            metricas_nivel_atual["nivel_medio"] -
            metricas_nivel_m1["nivel_medio"]
        )
    })

# ======================
# YOY
# ======================

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

if kpis_yoy:
    cards.append({
        "Comparação": "YoY",
        "Receita (%)": variacao_pct(
            kpis_atual["receita"], kpis_yoy["receita"]
        ),
        "Ocupação (pp)": (
            kpis_atual["ocupacao"] - kpis_yoy["ocupacao"]
        ),
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

# ======================
# DATAFRAME 3Meses
# ======================

df_comp = pd.DataFrame(cards)

periodos_3m = [
    periodo - 2,
    periodo - 1,
    periodo
]

labels_3m = [p.strftime("%b/%y") for p in periodos_3m]

# Receita
receita_3m = [
    df_res_comp[df_res_comp["mes_dt"] == p]["valor_mes"].sum()
    for p in periodos_3m
]

# Ocupação
ocupacao_3m = []
for p in periodos_3m:
    k = calcular_kpis_mes(df_res_comp, p)
    ocupacao_3m.append(k["ocupacao"] if k else 0)

# Tarifa Média
tarifa_3m = []
for p in periodos_3m:
    k = calcular_kpis_mes(df_res_comp, p)
    tarifa_3m.append(k["tarifa_media"] if k else 0)

# Cleaning
cleaning_3m = [
    calcular_kpis_hist_mes(df_hist_comp, p)["cleaning"] or 0
    for p in periodos_3m
]

# Adm
adm_3m = [
    calcular_kpis_hist_mes(df_hist_comp, p)["adm"] or 0
    for p in periodos_3m
]

# Atingimento Médio
ating_3m = [
    (calcular_metricas_nivel(df_res_comp, df_meta,
     p, partner_sel)["atingimento_medio"] or 0) * 100
    for p in periodos_3m
]

# Nível Médio
nivel_3m = [
    calcular_metricas_nivel(df_res_comp, df_meta, p, partner_sel)[
        "nivel_medio"] or 0
    for p in periodos_3m
]


def grafico_historico_3m(
    titulo,
    valores,
    labels,
    nome_barra,
    unidade="",
    cor_barra="#2563eb"
):
    # diferença do último mês
    delta = valores[-1] - valores[-2] if len(valores) >= 2 else None

    fig = go.Figure()

    fig.add_bar(
        x=labels,
        y=valores,
        name=nome_barra,
        marker_color=cor_barra,
        text=[f"{v:,.2f}{unidade}" for v in valores],
        textposition="outside"
    )

    fig.update_layout(
        title=f"{titulo}<br><sup>Δ último mês: {delta:+,.2f}{unidade if delta is not None else ''}</sup>",
        yaxis=dict(title=nome_barra),
        legend_title="",
        margin=dict(t=80, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)


st.subheader("📊 Histórico — Receita (Últimos 3 Meses)")
grafico_historico_3m(
    "Receita — Últimos 3 Meses",
    receita_3m,
    labels_3m,
    "Receita (R$)"
)

st.subheader("🏨 Histórico — Ocupação")
grafico_historico_3m(
    "Ocupação — Últimos 3 Meses",
    ocupacao_3m,
    labels_3m,
    "Ocupação (%)"
)

st.subheader("📊 Histórico — Tarifa Média")
grafico_historico_3m(
    "Tarifa Média — Últimos 3 Meses",
    tarifa_3m,
    labels_3m,
    "Tarifa Média (R$)"
)

st.subheader("🧹 Histórico — Cleaning Revenue")
grafico_historico_3m(
    "Cleaning Revenue — Últimos 3 Meses",
    cleaning_3m,
    labels_3m,
    "Cleaning Revenue (R$)"
)

st.subheader("🏷️ Histórico — Taxa Adm")
grafico_historico_3m(
    "Taxa Adm — Últimos 3 Meses",
    adm_3m,
    labels_3m,
    "Taxa Adm (R$)"
)

st.subheader("🎯 Histórico — Atingimento Médio")
grafico_historico_3m(
    "Atingimento Médio — Últimos 3 Meses",
    ating_3m,
    labels_3m,
    "Atingimento Médio (%)",
)

st.subheader("🧭 Histórico — Nível Médio")
grafico_historico_3m(
    "Nível Médio — Últimos 3 Meses",
    nivel_3m,
    labels_3m,
    "Nível Médio",
)

# ======================
# TABELA FINAL
# ======================

if df_comp.empty:
    st.info("Não há dados suficientes para comparativos temporais.")
else:
    df_comp_safe = df_comp.copy()

    colunas_formatadas = [
        "Receita (%)",
        "Ocupação (pp)",
        "Tarifa Média (%)",
        "Cleaning Revenue (%)",
        "Taxa Adm (%)",
        "Atingimento Médio (pp)",
        "Nível Médio (Δ)"
    ]

    colunas_existentes = [
        c for c in colunas_formatadas
        if c in df_comp_safe.columns
    ]

    df_comp_safe[colunas_existentes] = df_comp_safe[colunas_existentes].astype(
        float)

    st.markdown("#### 📋 Tabela de Comparativos Temporais")
    st.dataframe(
        df_comp_safe.style.format({
            # Receita
            "Receita Atual": "R$ {:,.0f}",
            "Receita M-1": "R$ {:,.0f}",
            "Δ Receita": "{:+,.0f}",
            "Receita (%)": "{:+.1f}%",

            # Ocupação
            "Ocupação Atual": "{:.1f}%",
            "Ocupação M-1": "{:.1f}%",
            "Δ Ocupação (pp)": "{:+.1f} pp",

            # Tarifa
            "Tarifa Atual": "R$ {:,.2f}",
            "Tarifa M-1": "R$ {:,.2f}",
            "Δ Tarifa": "{:+,.2f}",

            # Cleaning
            "Cleaning Atual": "R$ {:,.0f}",
            "Cleaning M-1": "R$ {:,.0f}",
            "Δ Cleaning": "{:+,.0f}",

            # Adm
            "Adm Atual": "R$ {:,.0f}",
            "Adm M-1": "R$ {:,.0f}",
            "Δ Adm": "{:+,.0f}",

            # Níveis
            "Atingimento Médio Atual (%)": "{:.1f}%",
            "Atingimento Médio M-1 (%)": "{:.1f}%",
            "Δ Atingimento Médio (pp)": "{:+.1f} pp",

            "Nível Médio Atual": "{:.2f}",
            "Nível Médio M-1": "{:.2f}",
            "Δ Nível Médio": "{:+.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

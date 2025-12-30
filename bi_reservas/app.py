# app.py

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="BI Reservas", layout="wide")

# ======================
# 1. INPUT DOS DADOS
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

    # 📌 Tabela principal de reservas
    ws_res = sh.worksheet(st.secrets["google_sheets"]["sheet_name"])
    df_reservas = pd.DataFrame(ws_res.get_all_records())
    df_reservas = df_reservas.rename(
        columns=lambda x: x.strip())  # limpa espaços

    # 📌 Tabela de metas / níveis (Base Níveis)
    ws_meta = sh.worksheet("Base Níveis")
    df_meta = pd.DataFrame(ws_meta.get_all_records())
    df_meta = df_meta.rename(
        columns=lambda x: x.strip().lower())  # normaliza nomes

    return df_reservas, df_meta


df, df_meta = load_data()

df["mes_dt"] = pd.to_datetime(df["mes"] + "-01")

# ======================
# 1. NORMALIZA TIPOS (BRL + QUANTIDADE)
# ======================


def parse_brl(series):
    return (
        series
        .astype(str)
        .str.strip()
        .str.replace("\u00a0", "", regex=False)      # espaço invisível
        .str.replace(".", "", regex=False)           # remove milhar
        .str.replace(",", ".", regex=False)          # decimal BR → US
        .str.replace(r"[^\d.-]", "", regex=True)     # remove R$, texto
        .replace("", "0")
        .astype(float)
    )


# colunas monetárias (BRL)
cols_money = ["valor_mes", "limpeza_mes"]

for col in cols_money:
    df[col] = parse_brl(df[col])

# noites = quantidade (NÃO moeda)
df["noites_mes"] = df["noites_mes"].astype(
    str).str.replace(",", ".").astype(float).astype(int)


# IDs (inteiros simples, sem nullable)
df["id_reserva"] = (
    df["id_reserva"]
    .astype(str)
    .str.replace(r"\D", "", regex=True)
    .astype(int)
)

df["id_propriedade"] = (
    df["id_propriedade"]
    .astype(str)
    .str.replace(r"\D", "", regex=True)
    .astype(int)
)

# ======================
# 2. COLUNAS ESPERADAS
# ======================
# id_reserva
# id_propriedade
# propriedade
# unidade
# canal
# noites_mes
# valor_mes
# limpeza_mes
# mes (YYYY-MM)
# partner

# ======================
# 3. FILTROS
# ======================

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    partner = st.selectbox(
        "Partner",
        ["Todos"] + sorted(df["partner"].unique())
    )

if partner != "Todos":
    predios_disponiveis = (
        df[df["partner"] == partner]["propriedade"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
else:
    predios_disponiveis = sorted(df["propriedade"].unique())

meses_ordenados = (
    df[["mes", "mes_dt"]]
    .drop_duplicates()
    .sort_values("mes_dt")["mes"]
    .tolist()
)

with col2:
    mes = st.selectbox("Mês", meses_ordenados)

with col3:
    propriedade = st.selectbox(
        "Prédio",
        ["Todos"] + predios_disponiveis
    )

if propriedade != "Todos":
    if partner != "Todos":
        unidades_disponiveis = (
            df[
                (df["partner"] == partner) &
                (df["propriedade"] == propriedade)
            ]["unidade"]
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
    else:
        unidades_disponiveis = (
            df[df["propriedade"] == propriedade]["unidade"]
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
else:
    unidades_disponiveis = []

with col4:
    if propriedade != "Todos":
        unidade = st.selectbox(
            "Unidade",
            ["Todas"] + unidades_disponiveis
        )
    else:
        unidade = "Todas"
        st.selectbox("Unidade", ["Selecione um prédio"], disabled=True)

with col5:
    canal = st.multiselect(
        "Canal",
        sorted(df["canal"].unique()),
        default=sorted(df["canal"].unique())
    )

# ======================
# 4. APLICA FILTROS
# ======================

df_f = df.copy()

if partner != "Todos":
    df_f = df_f[df_f["partner"] == partner]

df_f = df_f[df_f["mes"] == mes]

if propriedade != "Todos":
    df_f = df_f[df_f["propriedade"] == propriedade]

if unidade != "Todas":
    df_f = df_f[df_f["unidade"] == unidade]

if canal:
    df_f = df_f[df_f["canal"].isin(canal)]

# ======================
# 5. MÉTRICAS BASE
# ======================

reservas = df_f["id_reserva"].nunique()
noites = df_f["noites_mes"].sum()
receita_total = df_f["valor_mes"].sum()
receita_limpeza = df_f["limpeza_mes"].sum()
receita_diarias = receita_total - receita_limpeza

# Ocupação (simples, considerando 30 dias)
unidades_ativas = df_f[["id_propriedade", "unidade"]
                       ].drop_duplicates().shape[0]
noites_disponiveis = unidades_ativas * 30
ocupacao = noites / noites_disponiveis if noites_disponiveis > 0 else 0

# ======================
# 6. KPIs
# ======================

reservas = df_f["id_reserva"].nunique()
noites = df_f["noites_mes"].sum()
receita_total = df_f["valor_mes"].sum()
receita_limpeza = df_f["limpeza_mes"].sum()
receita_diarias = receita_total - receita_limpeza

periodo = pd.Period(mes, freq="M")
dias_no_mes = periodo.days_in_month

# ocupação (se for unidade única, cálculo direto; senão, média ponderada)
unidades_ativas = df_f[["id_propriedade", "unidade"]
                       ].drop_duplicates().shape[0]
noites_disponiveis = unidades_ativas * dias_no_mes
ocupacao = (noites / noites_disponiveis * 100) if noites_disponiveis > 0 else 0

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Reservas", reservas)
k2.metric("Ocupação (%)", f"{ocupacao:.1f}%")
k3.metric("Receita Total", f"R$ {receita_total:,.2f}")
k4.metric("Receita Diárias", f"R$ {receita_diarias:,.2f}")
k5.metric("Receita Limpeza", f"R$ {receita_limpeza:,.2f}")

# ======================
# 7. GRÁFICO DINÂMICO
# ======================

st.divider()

# Cabeçalho bonito quando unidade selecionada
if unidade != "Todas":
    st.markdown(
        f"### 🏠 {propriedade} — Unidade **{unidade}**"
    )
    st.caption(f"Resumo operacional da unidade no mês {mes}")

# se estiver filtrando unidade, não exibe gráfico agregado
if unidade == "Todas" and propriedade != "Todos":
    grafico_df = (
        df_f.groupby("unidade", as_index=False)
        .agg(receita=("valor_mes", "sum"))
    )
    fig = px.bar(
        grafico_df,
        x="unidade",
        y="receita",
        title=f"Receita por Unidade – {propriedade}"
    )

    st.plotly_chart(fig, use_container_width=True)

# ======================
# 7.1 HISTÓRICO MENSAL (BARRAS) — UNIDADE
# ======================

if propriedade != "Todos" and unidade != "Todas":
    ver_hist_unidade = st.toggle(
        "📊 Ver histórico mensal da unidade",
        value=False
    )

    if ver_hist_unidade:
        st.divider()
        st.subheader(f"📊 Histórico Mensal — {propriedade} | Unidade {unidade}")

        hist = (
            df[
                (df["propriedade"] == propriedade) &
                (df["unidade"] == unidade)
            ]
            .groupby(["mes", "mes_dt"], as_index=False)
            .agg(
                noites_ocupadas=("noites_mes", "sum"),
                receita_total=("valor_mes", "sum"),
                receita_limpeza=("limpeza_mes", "sum")
            )
            .sort_values("mes_dt")
        )

        hist["mes_fmt"] = (
            pd.to_datetime(hist["mes"] + "-01")
            .dt.strftime("%m-%Y")
        )

        hist["receita_diarias"] = hist["receita_total"] - \
            hist["receita_limpeza"]

        hist["dias_mes"] = (
            pd.to_datetime(hist["mes"] + "-01")
            .dt.days_in_month
        )

        hist["ocupacao"] = (
            hist["noites_ocupadas"] / hist["dias_mes"] * 100
        )

        hist["ADR"] = hist["receita_diarias"] / hist["noites_ocupadas"]

        col_h1, col_h2 = st.columns(2)

        with col_h1:
            fig_rec = px.bar(
                hist,
                x="mes_fmt",
                y="receita_total",
                title="Receita Total (R$) — Fechamento Mensal",
                text_auto=".2s"
            )

            st.plotly_chart(fig_rec, use_container_width=True)

        with col_h2:
            fig_occ = px.bar(
                hist,
                x="mes_fmt",
                y="ocupacao",
                title="Ocupação (%) — Fechamento Mensal",
                text_auto=".1f"
            )
            st.plotly_chart(fig_occ, use_container_width=True)

        fig_adr = px.bar(
            hist,
            x="mes_fmt",
            y="ADR",
            title="ADR (R$) — Fechamento Mensal",
            text_auto=".2f"
        )

        st.plotly_chart(fig_adr, use_container_width=True)

        hist["RevPAR"] = hist["ADR"] * (hist["ocupacao"] / 100)

        fig_revpar = px.bar(
            hist,
            x="mes_fmt",
            y="RevPAR",
            title="RevPAR (R$) — Fechamento Mensal",
            text_auto=".2f"
        )

        st.plotly_chart(fig_revpar, use_container_width=True)

        # =============================
        # 🔥 Cálculo do NÍVEL DA UNIDADE
        # =============================

        # Receita esperada (procura no De-para pelo nome da unidade)
        meta_linha = df_meta.loc[df_meta["unidade"]
                                 == unidade, "receita_esperada"]

        if not meta_linha.empty:
            valor_bruto = str(meta_linha.iloc[0]).strip()

            # normaliza (remove R$, pontos, troca vírgula...)
            valor_bruto = (
                valor_bruto.replace("R$", "")
                .replace(".", "")
                .replace(",", ".")
            )

            # tenta converter
            try:
                receita_esperada = float(valor_bruto)
            except ValueError:
                receita_esperada = None

            if receita_esperada and receita_esperada > 0:
                atingimento = receita_diarias / receita_esperada

                # Classificação do nível
                if atingimento < 0.5:
                    nivel = 1
                elif atingimento < 0.85:
                    nivel = 2
                elif atingimento < 1:
                    nivel = 3
                elif atingimento < 1.15:
                    nivel = 4
                else:
                    nivel = 5

                st.divider()
                st.subheader("📌 Indicador de Performance da Unidade")

                st.metric(
                    label="Nível da Unidade",
                    value=f"Nível {nivel}",
                    delta=f"Atingimento: {atingimento:.2%}"
                )

            else:
                st.warning(
                    "⚠️ Meta inválida ou não numérica para esta unidade.")

        else:
            st.warning("⚠️ Unidade não encontrada na aba 'Base Níveis'.")

# ======================
# 7.2 HISTÓRICO MENSAL (BARRAS) — PRÉDIO
# ======================

if propriedade != "Todos":

    ver_hist_predio = st.toggle(
        "📊 Ver histórico mensal do prédio",
        value=False
    )

    if ver_hist_predio:
        hist_p = (
            df[df["propriedade"] == propriedade]
            .groupby(["mes", "mes_dt"], as_index=False)
            .agg(
                noites_ocupadas=("noites_mes", "sum"),
                receita_total=("valor_mes", "sum"),
                receita_limpeza=("limpeza_mes", "sum"),
                unidades=("unidade", "nunique")
            )
            .sort_values("mes_dt")
        )

        hist_p["mes_fmt"] = (
            pd.to_datetime(hist_p["mes"] + "-01")
            .dt.strftime("%m-%Y")
        )

        hist_p["receita_diarias"] = hist_p["receita_total"] - \
            hist_p["receita_limpeza"]

        hist_p["dias_mes"] = (
            pd.to_datetime(hist_p["mes"] + "-01")
            .dt.days_in_month
        )

        hist_p["ocupacao"] = (
            hist_p["noites_ocupadas"] /
            (hist_p["dias_mes"] * hist_p["unidades"]) * 100
        )

        hist_p["ADR"] = hist_p["receita_diarias"] / hist_p["noites_ocupadas"]

        col_p1, col_p2 = st.columns(2)

        with col_p1:
            fig_rec_p = px.bar(
                hist_p,
                x="mes_fmt",
                y="receita_total",
                title="Receita Total (R$) — Prédio — Fechamento Mensal",
                text_auto=".2s"
            )
            st.plotly_chart(fig_rec_p, use_container_width=True)

        with col_p2:
            fig_occ_p = px.bar(
                hist_p,
                x="mes_fmt",
                y="ocupacao",
                title="Ocupação (%) — Prédio",
                text_auto=".1f"
            )
            st.plotly_chart(fig_occ_p, use_container_width=True)

            hist_p["RevPAR"] = hist_p["ADR"] * (hist_p["ocupacao"] / 100)

        fig_adr_p = px.bar(
            hist_p,
            x="mes_fmt",
            y="ADR",
            title="ADR (R$) — Prédio — Fechamento Mensal",
            text_auto=".2f"
        )

        st.plotly_chart(fig_adr_p, use_container_width=True)

        fig_revpar_p = px.bar(
            hist_p,
            x="mes_fmt",
            y="RevPAR",
            title="RevPAR (R$) — Prédio — Fechamento Mensal",
            text_auto=".2f"
        )

        st.plotly_chart(fig_revpar_p, use_container_width=True)

# ======================
# 8. DETALHE POR UNIDADE
# ======================

st.divider()
st.subheader("Detalhe por Unidade")

# --- calendário real do mês ---
periodo = pd.Period(mes, freq="M")
dias_no_mes = periodo.days_in_month

# agregação principal (SEM ordenação por ranking)
agg = (
    df_f.groupby(["id_propriedade", "propriedade", "unidade"])
    .agg(
        reservas=("id_reserva", "nunique"),
        noites_ocupadas=("noites_mes", "sum"),
        receita_total=("valor_mes", "sum"),
        receita_limpeza=("limpeza_mes", "sum")
    )
    .reset_index()
)

# métricas calculadas
agg["receita_diarias"] = agg["receita_total"] - agg["receita_limpeza"]
agg["ocupacao"] = (agg["noites_ocupadas"] / dias_no_mes) * 100
agg["ADR"] = agg["receita_diarias"] / agg["noites_ocupadas"]
agg["RevPAR"] = agg["ADR"] * (agg["ocupacao"] / 100)

# remove coluna técnica
agg = agg.drop(columns=["noites_ocupadas"])

# ordenação PADRÃO por ID (não ranking)
agg = agg.sort_values(["id_propriedade", "unidade"])

st.dataframe(
    agg,
    use_container_width=True,
    column_config={
        "ocupacao": st.column_config.NumberColumn(
            "Ocupação (%)",
            format="%.1f"
        ),
        "receita_total": st.column_config.NumberColumn(
            "Receita Total",
            format="R$ %.2f"
        ),
        "receita_diarias": st.column_config.NumberColumn(
            "Receita Diárias",
            format="R$ %.2f"
        ),
        "receita_limpeza": st.column_config.NumberColumn(
            "Receita Limpeza",
            format="R$ %.2f"
        ),
        "ADR": st.column_config.NumberColumn(
            "ADR",
            format="R$ %.2f"
        ),
        "RevPAR": st.column_config.NumberColumn(
            "RevPAR",
            format="R$ %.2f"
        )
    }
)

# ======================
# 9. SHARE DE CANAL


# ======================

st.subheader("Share de Canal (%)")

canal_share = (
    df_f.groupby("canal", as_index=False)["valor_mes"].sum()
)
canal_share["share"] = canal_share["valor_mes"] / \
    canal_share["valor_mes"].sum()

cores_canais = {
    "Airbnb": "#FF00CC",
    "Booking.com": "#0217FF",
    "Direct": "#02812C",
    "Direct_Partner": "#00CC7E",
    "Site": "#FF0000",
    "Expedia": "#EEFF00"
}

# Adiciona uma coluna com cor baseada no canal
canal_share["cor"] = canal_share["canal"].map(cores_canais)

fig_share = px.pie(
    canal_share,
    names="canal",
    values="valor_mes",
    title="Participação de Receita por Canal",
    hole=0.4,
    color="canal",
    color_discrete_map=cores_canais
)

fig_share.update_traces(
    textinfo="label+percent",
    hovertemplate="Canal: %{label}<br>Receita: R$ %{value:,.2f}<br>Share: %{percent}"
)

st.plotly_chart(fig_share, use_container_width=True)

# ======================
# 10. RANKINGS
# ======================

st.subheader("Ranking de Unidades")

ranking_unidade = agg.copy()

ranking_unidade = ranking_unidade.sort_values(
    "receita_total", ascending=False)
ranking_unidade = ranking_unidade[[
    "id_propriedade",
    "propriedade",
    "unidade",
    "receita_total",
    "receita_diarias",
    "receita_limpeza",
    "ocupacao",
    "ADR",
    "RevPAR"
]]

ranking_unidade.insert(0, "rank", range(1, len(ranking_unidade) + 1))

st.dataframe(
    ranking_unidade,
    use_container_width=True,
    column_config={
        "ocupacao": st.column_config.NumberColumn(
            "Ocupação (%)",
            format="%.1f"
        ),
        "receita_total": st.column_config.NumberColumn(
            "Receita Total",
            format="R$ %.2f"
        ),
        "receita_diarias": st.column_config.NumberColumn(
            "Receita Diárias",
            format="R$ %.2f"
        ),
        "receita_limpeza": st.column_config.NumberColumn(
            "Receita Limpeza",
            format="R$ %.2f"
        ),
        "ADR": st.column_config.NumberColumn(
            "ADR",
            format="R$ %.2f"
        ),
        "RevPAR": st.column_config.NumberColumn(
            "RevPAR",
            format="R$ %.2f"
        )
    }
)

st.subheader("Ranking de Prédios")

ranking_predio = (
    agg.groupby(["id_propriedade", "propriedade"], as_index=False)
    .agg(
        receita_total=("receita_total", "sum"),
        receita_diarias=("receita_diarias", "sum"),
        receita_limpeza=("receita_limpeza", "sum"),
        ocupacao_media=("ocupacao", "mean"),
        ADR_medio=("ADR", "mean"),
        RevPAR_medio=("RevPAR", "mean")
    )
)

ranking_predio = ranking_predio.sort_values("receita_total", ascending=False)
ranking_predio.insert(0, "rank", range(1, len(ranking_predio) + 1))

st.dataframe(
    ranking_predio,
    use_container_width=True,
    column_config={
        "ocupacao_media": st.column_config.NumberColumn(
            "Ocupação Média (%)",
            format="%.1f"
        ),
        "receita_total": st.column_config.NumberColumn(
            "Receita Total",
            format="R$ %.2f"
        ),
        "receita_diarias": st.column_config.NumberColumn(
            "Receita Diárias",
            format="R$ %.2f"
        ),
        "receita_limpeza": st.column_config.NumberColumn(
            "Receita Limpeza",
            format="R$ %.2f"
        ),
        "ADR_medio": st.column_config.NumberColumn(
            "ADR Médio",
            format="R$ %.2f"
        ),
        "RevPAR_medio": st.column_config.NumberColumn(
            "RevPAR Médio",
            format="R$ %.2f"
        )
    }
)

# ======================
# 11. MÉTRICAS AVANÇADAS (OK)
# ======================
# BI agora contém:
# - Ocupação real por calendário
# - ADR
# - RevPAR
# - Share de canal
# - Ranking operacional

# ======================
# - ADR = receita_diarias / noites
# - Receita por unidade disponível (RevPAR)
# - Participação % por canal

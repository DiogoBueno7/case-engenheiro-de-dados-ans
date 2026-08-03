"""
Dashboard Streamlit — camada de visualização/BI do case.

Consome a camada **Gold** (curada) do pipeline Medallion, materializada nos CSVs
de `output/`. É o equivalente local a uma ferramenta de BI (Amazon QuickSight /
Power BI / Databricks Dashboards) lendo do warehouse (Redshift/Gold): não
reprocessa os 4,8M de registros — apenas apresenta os agregados já prontos.

Mostra as 3 respostas do case (a/b/c) e alguns insights extras
(concentração de mercado e perfil demográfico).

Roda via container próprio (serviço `streamlit` do docker-compose):
    http://localhost:8501
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

OUTPUT_DIR = Path("/app/output")
COMPETENCIA = "2025-08"

# Ordem natural das faixas etárias (o CSV vem ordenado por quantidade, não por idade).
FAIXA_ORDER = [
    "0 a 4 anos",
    "5 a 9 anos",
    "10 a 14 anos",
    "15 a 19 anos",
    "20 a 24 anos",
    "25 a 29 anos",
    "30 a 34 anos",
    "35 a 39 anos",
    "40 a 44 anos",
    "45 a 49 anos",
    "50 a 54 anos",
    "55 a 59 anos",
    "60 a 64 anos",
    "65 a 69 anos",
    "70 a 74 anos",
    "75 a 79 anos",
    "80 anos ou mais",
]

st.set_page_config(
    page_title="Case ANS — Beneficiários SP",
    page_icon="🏥",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Carga dos dados (com cache). Cada CSV é uma tabela da camada Gold.
# ---------------------------------------------------------------------------
@st.cache_data
def load_csv(name: str) -> pd.DataFrame | None:
    path = OUTPUT_DIR / f"{name}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def fmt(n: float) -> str:
    """Formata inteiro grande no padrão brasileiro (ponto como separador de milhar)."""
    return f"{int(n):,}".replace(",", ".")


# Distribuições completas (insight_*) quando disponíveis; senão, as versões
# reduzidas das respostas do case (top5 / top1) como fallback.
operadoras = load_csv("insight_operadoras")
if operadoras is None:
    operadoras = load_csv("a_top5_operadoras")

faixa = load_csv("insight_faixa_etaria")
if faixa is None:
    faixa = load_csv("b_faixa_etaria_top")

municipios = load_csv("c_beneficiarios_por_municipio")

st.title("🏥 Beneficiários de Planos de Saúde — São Paulo")
st.caption(
    f"Dados abertos da ANS · competência {COMPETENCIA} · "
    "camada Gold do pipeline Medallion (Bronze → Silver → Gold)"
)

if municipios is None and operadoras is None and faixa is None:
    st.error(
        "Nenhum resultado encontrado em `output/`. "
        "Rode o pipeline primeiro:\n\n"
        "`docker compose exec spark python -m src.run_pipeline`"
    )
    st.stop()

# ---------------------------------------------------------------------------
# KPIs de topo — visão geral rápida.
# ---------------------------------------------------------------------------
# O total de beneficiários é a soma dos agregados (qualquer uma das dimensões
# dá o mesmo total, pois são cortes da mesma base).
total_benef = None
for df in (municipios, operadoras, faixa):
    if df is not None:
        total_benef = int(df["qt_beneficiarios_ativos"].sum())
        break

c1, c2, c3, c4 = st.columns(4)
c1.metric("Beneficiários ativos", fmt(total_benef) if total_benef else "—")
c2.metric("Operadoras", fmt(len(operadoras)) if operadoras is not None else "—")
c3.metric("Municípios", fmt(len(municipios)) if municipios is not None else "—")
if faixa is not None:
    lider = faixa.sort_values("qt_beneficiarios_ativos", ascending=False).iloc[0]
    c4.metric("Faixa etária líder", str(lider["de_faixa_etaria"]))

st.divider()

# ---------------------------------------------------------------------------
# (a) Operadoras
# ---------------------------------------------------------------------------
st.subheader("(a) Operadoras com mais beneficiários ativos")

if operadoras is not None:
    op = operadoras.sort_values("qt_beneficiarios_ativos", ascending=False).copy()
    col_a, col_b = st.columns([2, 1])

    top_n = op.head(10)
    chart = (
        alt.Chart(top_n)
        .mark_bar(color="#1f77b4")
        .encode(
            x=alt.X("qt_beneficiarios_ativos:Q", title="Beneficiários ativos"),
            y=alt.Y("nm_razao_social:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("nm_razao_social:N", title="Operadora"),
                alt.Tooltip("qt_beneficiarios_ativos:Q", title="Ativos", format=","),
            ],
        )
        .properties(height=350)
    )
    col_a.altair_chart(chart, use_container_width=True)

    # Insight extra: concentração de mercado.
    if total_benef:
        share_lider = op.iloc[0]["qt_beneficiarios_ativos"] / total_benef
        share_top5 = op.head(5)["qt_beneficiarios_ativos"].sum() / total_benef
        col_b.markdown("**Concentração de mercado**")
        col_b.metric("Líder de mercado", str(op.iloc[0]["nm_razao_social"]))
        col_b.metric("Share do líder", f"{share_lider:.1%}")
        col_b.metric("Share das 5 maiores", f"{share_top5:.1%}")
        col_b.caption(
            "Uma operadora pode aparecer em vários beneficiários (médico + "
            "odontológico), por isso os shares somam mais que a base de pessoas."
        )

    with st.expander("Ver as 5 maiores (resposta do case)"):
        st.dataframe(
            op.head(5).rename(
                columns={
                    "cd_operadora": "Código",
                    "nm_razao_social": "Operadora",
                    "qt_beneficiarios_ativos": "Beneficiários ativos",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
else:
    st.info("Sem dados de operadoras em `output/`.")

st.divider()

# ---------------------------------------------------------------------------
# (b) Faixa etária
# ---------------------------------------------------------------------------
st.subheader("(b) Distribuição por faixa etária")

if faixa is not None and len(faixa) > 1:
    fx = faixa.copy()
    fx["de_faixa_etaria"] = pd.Categorical(
        fx["de_faixa_etaria"], categories=FAIXA_ORDER, ordered=True
    )
    fx = fx.sort_values("de_faixa_etaria")
    lider_faixa = faixa.sort_values("qt_beneficiarios_ativos", ascending=False).iloc[0]

    chart = (
        alt.Chart(fx)
        .mark_bar()
        .encode(
            x=alt.X("de_faixa_etaria:N", sort=FAIXA_ORDER, title="Faixa etária"),
            y=alt.Y("qt_beneficiarios_ativos:Q", title="Beneficiários ativos"),
            color=alt.condition(
                alt.datum.de_faixa_etaria == str(lider_faixa["de_faixa_etaria"]),
                alt.value("#d62728"),
                alt.value("#1f77b4"),
            ),
            tooltip=[
                alt.Tooltip("de_faixa_etaria:N", title="Faixa"),
                alt.Tooltip("qt_beneficiarios_ativos:Q", title="Ativos", format=","),
            ],
        )
        .properties(height=350)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption(
        f"Faixa líder (destaque): **{lider_faixa['de_faixa_etaria']}** com "
        f"**{fmt(lider_faixa['qt_beneficiarios_ativos'])}** beneficiários ativos."
    )
elif faixa is not None:
    # Só o top 1 (fallback sem o export completo).
    lider_faixa = faixa.iloc[0]
    st.metric(
        f"Faixa etária líder — {lider_faixa['de_faixa_etaria']}",
        fmt(lider_faixa["qt_beneficiarios_ativos"]),
    )
    st.info(
        "Distribuição completa disponível após rodar o pipeline com o export de "
        "insights (`insight_faixa_etaria.csv`)."
    )
else:
    st.info("Sem dados de faixa etária em `output/`.")

st.divider()

# ---------------------------------------------------------------------------
# (c) Municípios
# ---------------------------------------------------------------------------
st.subheader("(c) Beneficiários por município")

if municipios is not None:
    mun = municipios.sort_values("qt_beneficiarios_ativos", ascending=False).copy()
    col_a, col_b = st.columns([2, 1])

    top_n = mun.head(15)
    chart = (
        alt.Chart(top_n)
        .mark_bar(color="#2ca02c")
        .encode(
            x=alt.X("qt_beneficiarios_ativos:Q", title="Beneficiários ativos"),
            y=alt.Y("nm_municipio:N", sort="-x", title=None),
            tooltip=[
                alt.Tooltip("nm_municipio:N", title="Município"),
                alt.Tooltip("qt_beneficiarios_ativos:Q", title="Ativos", format=","),
            ],
        )
        .properties(height=450)
    )
    col_a.altair_chart(chart, use_container_width=True)

    # Insight extra: concentração geográfica na capital.
    if total_benef:
        capital = mun[mun["nm_municipio"].str.strip().str.lower() == "são paulo"]
        col_b.markdown("**Concentração geográfica**")
        if not capital.empty:
            share_cap = capital.iloc[0]["qt_beneficiarios_ativos"] / total_benef
            col_b.metric("Capital (São Paulo)", f"{share_cap:.1%}")
        share_top10 = mun.head(10)["qt_beneficiarios_ativos"].sum() / total_benef
        col_b.metric("Top 10 municípios", f"{share_top10:.1%}")
        col_b.metric("Total de municípios", fmt(len(mun)))

    with st.expander(f"Ver todos os {len(mun)} municípios (ordem decrescente)"):
        busca = st.text_input("Filtrar por nome do município", "")
        tabela = mun
        if busca:
            tabela = mun[mun["nm_municipio"].str.contains(busca, case=False, na=False)]
        st.dataframe(
            tabela.rename(
                columns={
                    "cd_municipio": "Código",
                    "nm_municipio": "Município",
                    "qt_beneficiarios_ativos": "Beneficiários ativos",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
else:
    st.info("Sem dados de municípios em `output/`.")

st.divider()
st.caption(
    "Fonte: Dados Abertos da ANS · Pipeline Medallion (PySpark + Delta Lake + MinIO) · "
    "Dashboard servindo a camada Gold curada."
)

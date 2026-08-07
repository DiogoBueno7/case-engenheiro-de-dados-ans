"""
Dashboard Streamlit — camada de visualização/BI do case.

Consome a camada **Gold** (curada) do pipeline Medallion, materializada nos CSVs
de `output/`. É o equivalente local a uma ferramenta de BI (Amazon QuickSight /
Power BI / Databricks Dashboards) lendo do warehouse (Redshift/Gold): não
reprocessa os 4,8M de registros — apenas apresenta os agregados já prontos.

Mostra as 3 respostas do case (a/b/c) e alguns insights extras
(concentração de mercado e perfil demográfico).

Visualizações em **Plotly** (interativas, tema coeso, formatação numérica BR).

Roda via container próprio (serviço `streamlit` do docker-compose):
    http://localhost:8501
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

OUTPUT_DIR = Path("/app/output")
COMPETENCIA = "2025-08"

# ---------------------------------------------------------------------------
# Identidade visual — uma única paleta reaproveitada em todos os gráficos.
# ---------------------------------------------------------------------------
PRIMARY = "#2563EB"      # azul — cor institucional dos gráficos
LEADER = "#F97316"       # laranja — destaque do item líder
# Cor do texto dos gráficos (rótulos de dados + nomes das categorias no eixo).
# Clara de propósito: o tema é fixado em escuro (app/.streamlit/config.toml), então
# o texto precisa ser claro para aparecer sobre o fundo preto. Antes usava um tom
# quase preto (#1E293B), que sumia no fundo escuro.
TEXT = "#E2E8F0"         # slate-200 — texto claro, legível no tema escuro
FONT = "Inter, Segoe UI, system-ui, -apple-system, sans-serif"

# Tooltip (hover) — caixa escura de alto contraste, legível tanto no tema claro
# quanto no escuro. O padrão do Plotly (fundo branco) some no tema escuro; como
# a caixa é um elemento flutuante próprio, fixá-la em escuro funciona nos dois.
HOVER_BG = "rgba(15,23,42,0.96)"        # slate-900 translúcido
HOVER_FG = "#F8FAFC"                     # texto quase branco
HOVER_ACCENT = "#93C5FD"                 # azul claro para o rótulo da métrica
HOVER_BORDER = "rgba(148,163,184,0.35)"  # borda tênue (slate-400)

# Escala sequencial (cor por magnitude) — reforça a leitura do ranking.
SCALE_BLUE = ["#DBEAFE", "#93C5FD", "#3B82F6", "#1D4ED8"]

# Modebar do Plotly desligada: dashboard de leitura, não de edição.
PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}

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

# CSS mínimo e seguro para os KPIs: o "card" (borda + cantos arredondados) vem
# do st.container(border=True) nativo — aqui só damos padding/altura uniforme e
# centralizamos o conteúdo. Sem mexer em background nem cores para não brigar
# com o tema (claro/escuro) do Streamlit.
st.markdown(
    """
    <style>
    /* Esconde a barra de "decoração" do topo (data-testid=stDecoration): um
       gradiente laranja fino que o Streamlit desenha por padrão e que parece um
       loading perpétuo. Não tem função — é puramente estética. */
    [data-testid="stDecoration"] {
        display: none;
    }

    /* Reduz o respiro padrão no topo da página (o block-container vem com um
       padding-top grande). Sobe todo o conteúdo alguns pixels. */
    .block-container {
        padding-top: 4rem;
    }

    /* Só os containers com borda que envolvem uma métrica viram card estilizado. */
    div[data-testid="stMetric"] {
        text-align: center;
        padding: 4px 2px;
    }
    div[data-testid="stMetric"] label {
        justify-content: center;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers de visualização (tema único aplicado a todo gráfico).
# ---------------------------------------------------------------------------
def _style(fig: go.Figure, height: int) -> go.Figure:
    """Aplica o tema comum: fundo transparente, fonte, grid suave, número BR."""
    fig.update_layout(
        height=height,
        template="plotly_white",
        font=dict(family=FONT, size=13, color=TEXT),
        margin=dict(l=8, r=28, t=12, b=8),
        separators=",.",  # decimal vírgula, milhar ponto (padrão brasileiro)
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor=HOVER_BG,
            bordercolor=HOVER_BORDER,
            font=dict(family=FONT, size=13, color=HOVER_FG),
            align="left",
        ),
        showlegend=False,
    )
    return fig


def barras_horizontais(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    value_title: str,
    scale: list[str],
    height: int,
) -> go.Figure:
    """Ranking em barras horizontais: maior no topo, rótulo de valor e cor por magnitude."""
    d = df.sort_values(value_col, ascending=True)  # ascendente => maior no topo
    vmax = d[value_col].max()
    fig = go.Figure(
        go.Bar(
            x=d[value_col],
            y=d[label_col],
            orientation="h",
            marker=dict(
                color=d[value_col],
                colorscale=scale,
                line=dict(width=0),
            ),
            text=d[value_col],
            texttemplate="%{text:,.0f}",
            textposition="outside",
            textfont=dict(size=12, color=TEXT),
            cliponaxis=False,
            hovertemplate=(
                f"<b>%{{y}}</b><br>"
                f"<span style='color:{HOVER_ACCENT}'>{value_title}:</span> "
                f"<b>%{{x:,.0f}}</b><extra></extra>"
            ),
        )
    )
    _style(fig, height)
    # Eixo de valores oculto: com o rótulo de dados em cada barra, os ticks
    # numéricos e a grade ficariam redundantes. Mantém-se só a folga à direita
    # (range) para o rótulo externo não ser cortado.
    fig.update_xaxes(
        title=None,
        showgrid=False,
        showticklabels=False,
        zeroline=False,
        range=[0, vmax * 1.18],
    )
    fig.update_yaxes(title=None, showgrid=False, zeroline=False)
    return fig


def fmt(n: float) -> str:
    """Formata inteiro grande no padrão brasileiro (ponto como separador de milhar)."""
    return f"{int(n):,}".replace(",", ".")


def ranking_cards(df: pd.DataFrame, label_col: str, value_col: str, total: int) -> str:
    """Monta um 'leaderboard' em HTML: badge de posição, barra de proporção e
    percentual de participação. Substitui a tabela crua por algo apresentável.

    Cores e superfícies são semitransparentes (tons de slate) para funcionar
    tanto no tema claro quanto no escuro do Streamlit — sem fixar preto/branco.
    O líder (1º) ganha o laranja de destaque, coerente com a aba (b).
    """
    # IMPORTANTE: o HTML precisa sair "minificado", numa linha só e sem
    # indentação. O Streamlit renderiza via Markdown e qualquer linha com 4+
    # espaços no início vira bloco de código (<pre>), quebrando os cards.
    vmax = df[value_col].max()
    card_css = (
        "display:flex;align-items:center;gap:14px;padding:12px 14px;"
        "border:1px solid rgba(148,163,184,0.18);border-radius:12px;"
        "background:rgba(148,163,184,0.06);"
    )
    cards = []
    for i, (_, row) in enumerate(df.iterrows()):
        rank = i + 1
        qt = int(row[value_col])
        share = (qt / total * 100) if total else 0
        share_str = f"{share:.1f}%".replace(".", ",")
        fill = (qt / vmax * 100) if vmax else 0
        accent = LEADER if rank == 1 else PRIMARY
        cards.append(
            f'<div style="{card_css}">'
            f'<div style="flex:0 0 34px;height:34px;border-radius:50%;background:{accent};'
            f'color:#fff;font-weight:700;font-size:15px;display:flex;align-items:center;'
            f'justify-content:center;">{rank}</div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-weight:600;font-size:14px;line-height:1.25;'
            f'margin-bottom:6px;">{row[label_col]}</div>'
            f'<div style="height:6px;border-radius:6px;background:rgba(148,163,184,0.20);'
            f'overflow:hidden;"><div style="width:{fill:.1f}%;height:100%;background:{accent};'
            f'border-radius:6px;"></div></div>'
            f'</div>'
            f'<div style="flex:0 0 auto;text-align:right;">'
            f'<div style="font-weight:700;font-size:15px;line-height:1.2;">{fmt(qt)}</div>'
            f'<div style="font-size:12px;opacity:0.6;">{share_str}</div>'
            f'</div>'
            f'</div>'
        )
    return (
        f'<div style="display:flex;flex-direction:column;gap:10px;'
        f'font-family:{FONT};">{"".join(cards)}</div>'
    )


def stat_card(
    label: str, value: str, sub: str = "", accent: str = PRIMARY, info: str = ""
) -> str:
    """Card de estatística (rótulo + valor grande + subtexto), acento à esquerda.
    Se `info` for passado, adiciona um "ⓘ" ao lado do rótulo com tooltip nativo
    (atributo `title`) — aparece ao passar o mouse.
    HTML minificado em linha única (o Markdown do Streamlit trata linha indentada
    como bloco de código)."""
    sub_html = (
        f'<div style="font-size:12px;opacity:0.6;margin-top:2px;">{sub}</div>'
        if sub
        else ""
    )
    # Aspas do title escapadas para não quebrar o atributo HTML.
    info_html = (
        f'<span title="{info.replace(chr(34), "&quot;")}" '
        f'style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:15px;height:15px;margin-left:6px;border-radius:50%;'
        f'border:1px solid rgba(148,163,184,0.6);font-size:10px;font-weight:700;'
        f'cursor:help;opacity:0.7;vertical-align:middle;">i</span>'
        if info
        else ""
    )
    return (
        f'<div style="padding:14px 16px;border:1px solid rgba(148,163,184,0.18);'
        f'border-left:4px solid {accent};border-radius:12px;'
        f'background:rgba(148,163,184,0.06);font-family:{FONT};">'
        f'<div style="font-size:12px;letter-spacing:.03em;text-transform:uppercase;'
        f'opacity:0.65;">{label}{info_html}</div>'
        f'<div style="font-weight:700;font-size:22px;line-height:1.25;'
        f'margin-top:2px;">{value}</div>{sub_html}</div>'
    )


# ---------------------------------------------------------------------------
# Carga dos dados (com cache). Cada CSV é uma tabela da camada Gold.
# ---------------------------------------------------------------------------
@st.cache_data
def _read_csv(path: str, mtime: float) -> pd.DataFrame:
    """Lê o CSV. Cacheado por (caminho, mtime): quando o arquivo muda no disco,
    a chave muda e a leitura é refeita — sem servir dado velho."""
    return pd.read_csv(path)


def load_csv(name: str) -> pd.DataFrame | None:
    # A checagem de existência fica FORA do cache de propósito: se cacheássemos o
    # `None` de um arquivo ausente (como era antes), o dashboard subia vazio e
    # continuava vazio mesmo depois do pipeline gerar o CSV — só um restart do
    # container resolvia. Assim o miss nunca é cacheado e o arquivo é relido assim
    # que aparece.
    path = OUTPUT_DIR / f"{name}.csv"
    if not path.exists():
        return None
    return _read_csv(str(path), path.stat().st_mtime)


# Distribuições completas (insight_*) quando disponíveis; senão, as versões
# reduzidas das respostas do case (top5 / top1) como fallback.
operadoras = load_csv("insight_operadoras")
if operadoras is None:
    operadoras = load_csv("a_top5_operadoras")

faixa = load_csv("insight_faixa_etaria")
if faixa is None:
    faixa = load_csv("b_faixa_etaria_top")

municipios = load_csv("c_beneficiarios_por_municipio")

if municipios is None and operadoras is None and faixa is None:
    st.error(
        "Nenhum resultado encontrado em `output/`. "
        "Rode o pipeline primeiro:\n\n"
        "`docker compose exec spark python -m src.run_pipeline`"
    )
    st.stop()

# O total de beneficiários é a soma dos agregados (qualquer uma das dimensões
# dá o mesmo total, pois são cortes da mesma base). Usado adiante na aba (c)
# para calcular a concentração geográfica.
total_benef = None
for df in (municipios, operadoras, faixa):
    if df is not None:
        total_benef = int(df["qt_beneficiarios_ativos"].sum())
        break

# ---------------------------------------------------------------------------
# Navegação em abas: visão geral do case + uma aba por resposta (a/b/c).
# Antes era uma única página rolável ("linguição"); as abas separam o contexto
# do case de cada resposta.
# ---------------------------------------------------------------------------
tab_case, tab_a, tab_b, tab_c = st.tabs(
    [
        "📋 O Case",
        "🏢 (a) Operadoras",
        "👥 (b) Faixa etária",
        "🗺️ (c) Municípios",
    ]
)

# ===========================================================================
# Aba: O Case — apresenta as 3 perguntas a responder e o resumo das respostas.
# ===========================================================================
with tab_case:
    # st.title("🏥 Beneficiários de Planos de Saúde")
    # st.caption(
    #     f"Dados abertos da ANS · competência {COMPETENCIA} · "
    #     "camada Gold do pipeline Medallion (Bronze → Silver → Gold)"
    # )
    # st.divider()

    st.title("Desafio 🏥")
    st.markdown(
        "A partir dos **dados abertos da ANS** de beneficiários de planos de "
        f"saúde de São Paulo (competência **{COMPETENCIA}**, {fmt(4830707)} "
        "registros brutos), o case pede a resposta de **três perguntas**. "
        "Cada uma tem uma aba própria acima, com o gráfico e os dados de apoio."
    )
    st.markdown("")

    st.markdown("**Consultas solicitadas** — a partir dos dados processados, responda:")

    # Texto EXATO do documento do case (com os mesmos destaques em negrito).
    # Cada pergunta ocupa a largura toda, em seu próprio card, para não picotar.
    perguntas = [
        ("a", "Quais são as **5 operadoras** com **maior número de beneficiários ativos**?"),
        ("b", "Qual é a **faixa etária com mais beneficiários** e **quantos** são?"),
        ("c", "Liste, de forma **decrescente**, a **quantidade de beneficiários por município**."),
    ]
    for letra, pergunta in perguntas:
        with st.container(border=True):
            st.markdown(f"**({letra})** {pergunta}")

    st.divider()
    # st.caption(
    #     "As respostas acima são o resumo; abra cada aba para o gráfico completo, "
    #     "os insights e a tabela de apoio."
    # )

# ===========================================================================
# Aba (a): Operadoras
# ===========================================================================
with tab_a:
    st.subheader("(a) Operadoras com mais beneficiários ativos")

    if operadoras is not None:
        op = operadoras.sort_values("qt_beneficiarios_ativos", ascending=False).copy()
        total_op = int(op["qt_beneficiarios_ativos"].sum())

        # Gráfico (TOP 10) e ranking (TOP 5) lado a lado. O percentual dos cards
        # é a participação sobre o total de beneficiários por operadora.
        col_graf, col_rank = st.columns([1.35, 1], gap="large")

        with col_graf:
            st.caption("Ranking das 10 maiores")
            with st.container(border=True):
                top_n = op.head(10)
                fig = barras_horizontais(
                    top_n,
                    label_col="nm_razao_social",
                    value_col="qt_beneficiarios_ativos",
                    value_title="Beneficiários ativos",
                    scale=SCALE_BLUE,
                    height=430,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        with col_rank:
            st.caption("As 5 maiores (resposta do case)")
            st.markdown(
                ranking_cards(
                    op.head(5),
                    label_col="nm_razao_social",
                    value_col="qt_beneficiarios_ativos",
                    total=total_op,
                ),
                unsafe_allow_html=True,
            )
    else:
        st.info("Sem dados de operadoras em `output/`.")

# ===========================================================================
# Aba (b): Faixa etária
# ===========================================================================
with tab_b:
    st.subheader("(b) Distribuição por faixa etária")

    if faixa is not None and len(faixa) > 1:
        fx = faixa.copy()
        fx["de_faixa_etaria"] = pd.Categorical(
            fx["de_faixa_etaria"], categories=FAIXA_ORDER, ordered=True
        )
        # Descarta faixas fora da ordem oficial (valores nulos ou desconhecidos
        # viram NaN na conversão acima) — sem isso apareceria uma barra "nan".
        fx = fx.dropna(subset=["de_faixa_etaria"])
        fx = fx.sort_values("de_faixa_etaria")
        lider_faixa = faixa.sort_values(
            "qt_beneficiarios_ativos", ascending=False
        ).iloc[0]
        lider_nome = str(lider_faixa["de_faixa_etaria"])
        lider_qt = int(lider_faixa["qt_beneficiarios_ativos"])
        total_fx = int(faixa["qt_beneficiarios_ativos"].sum())
        lider_share = f"{lider_qt / total_fx * 100:.1f}%".replace(".", ",")

        # Card de destaque da faixa líder (acento laranja, coerente com a barra
        # destacada no gráfico). HTML minificado — linha única sem indentação,
        # senão o Markdown do Streamlit o trata como bloco de código.
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:16px;padding:16px 20px;'
            f'border:1px solid rgba(148,163,184,0.18);border-left:4px solid {LEADER};'
            f'border-radius:12px;background:rgba(249,115,22,0.06);'
            f'font-family:{FONT};margin-bottom:18px;">'
            f'<div style="font-size:30px;line-height:1;">🏆</div>'
            f'<div style="flex:1;">'
            f'<div style="font-size:12px;letter-spacing:.04em;text-transform:uppercase;'
            f'opacity:0.65;margin-bottom:2px;">Faixa etária líder</div>'
            f'<div style="font-weight:700;font-size:20px;line-height:1.2;">{lider_nome}</div>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<div style="font-weight:700;font-size:22px;line-height:1.2;color:{LEADER};">'
            f'{fmt(lider_qt)}</div>'
            f'<div style="font-size:12px;opacity:0.65;">beneficiários ativos · '
            f'{lider_share} do total</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Barra vertical em ordem de idade; a faixa líder ganha cor de destaque.
        cores = [LEADER if v == lider_nome else PRIMARY for v in fx["de_faixa_etaria"]]
        fig = go.Figure(
            go.Bar(
                x=fx["de_faixa_etaria"].astype(str),
                y=fx["qt_beneficiarios_ativos"],
                marker=dict(color=cores, line=dict(width=0)),
                text=fx["qt_beneficiarios_ativos"],
                texttemplate="%{text:,.0f}",
                textposition="outside",
                textfont=dict(size=11, color=TEXT),
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    f"<span style='color:{HOVER_ACCENT}'>Beneficiários ativos:</span> "
                    "<b>%{y:,.0f}</b><extra></extra>"
                ),
            )
        )
        _style(fig, height=420)
        fig.update_xaxes(title=None, showgrid=False, zeroline=False, tickangle=-40)
        # Eixo de valores oculto: o rótulo em cada barra já traz o número, então
        # os ticks e a grade horizontal seriam redundantes.
        fig.update_yaxes(
            title=None,
            showgrid=False,
            showticklabels=False,
            zeroline=False,
        )
        fig.update_layout(margin=dict(l=8, r=8, t=24, b=8))
        with st.container(border=True):
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("A faixa em destaque (laranja) no gráfico é a líder.")
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

# ===========================================================================
# Aba (c): Municípios
# ===========================================================================
with tab_c:
    st.subheader("(c) Beneficiários por município")

    if municipios is not None:
        mun = municipios.sort_values("qt_beneficiarios_ativos", ascending=False).copy()

        n_mun = len(mun)
        total_mun = int(mun["qt_beneficiarios_ativos"].sum())
        lider = mun.iloc[0]
        lider_share = f"{int(lider['qt_beneficiarios_ativos']) / total_mun * 100:.1f}%".replace(".", ",")
        top5_share = f"{mun.head(5)['qt_beneficiarios_ativos'].sum() / total_mun * 100:.1f}%".replace(".", ",")
        top10_share = f"{mun.head(10)['qt_beneficiarios_ativos'].sum() / total_mun * 100:.1f}%".replace(".", ",")

        col_graf, col_insight = st.columns([1.5, 1], gap="large")

        with col_graf:
            st.caption("Ranking dos 15 maiores")
            with st.container(border=True):
                top_n = mun.head(15)
                fig = barras_horizontais(
                    top_n,
                    label_col="nm_municipio",
                    value_col="qt_beneficiarios_ativos",
                    value_title="Beneficiários ativos",
                    scale=SCALE_BLUE,
                    height=520,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        with col_insight:
            st.caption("Destaques")
            st.markdown(
                f'<div style="display:flex;flex-direction:column;gap:12px;">'
                + stat_card(
                    "Município líder",
                    str(lider["nm_municipio"]),
                    f"{fmt(lider['qt_beneficiarios_ativos'])} · {lider_share} do total",
                    accent=LEADER,
                )
                + stat_card("Municípios com beneficiários", fmt(n_mun))
                + stat_card(
                    "Concentração geográfica",
                    f"{top5_share}",
                    f"nos 5 maiores municípios · {top10_share} nos 10 maiores",
                    info=(
                        "O mercado é muito concentrado em poucas cidades (São Paulo "
                        "capital + região metropolitana). Pouquíssimos municípios "
                        "respondem pela maior parte dos beneficiários, enquanto a "
                        "grande maioria das 646 cidades divide a fatia restante."
                    ),
                )
                + "</div>",
                unsafe_allow_html=True,
            )

        # Tabela completa (todos os municípios) — a resposta literal do case:
        # "liste, de forma decrescente, a quantidade de beneficiários por
        # município". Recolhível (não polui a visão de topo) e paginada, pois são
        # centenas de linhas. O Streamlit não tem paginação nativa em tabela;
        # implementamos com um seletor de página fatiando o DataFrame já ordenado.
        with st.expander(f"📋 Tabela completa — todos os {fmt(n_mun)} municípios (decrescente)"):
            tabela = mun.reset_index(drop=True).copy()
            tabela.insert(0, "Posição", tabela.index + 1)
            tabela["Participação"] = (
                tabela["qt_beneficiarios_ativos"] / total_mun * 100
            )

            # Ao trocar o tamanho da página, volta para a 1ª. Sem isso, o valor
            # guardado em session_state (ex.: página 13 com 50 linhas) podia ficar
            # acima do novo total de páginas (ex.: 3 páginas com 250 linhas) e o
            # number_input estourava StreamlitAPIException — travando a aba (c).
            def _reset_mun_pagina() -> None:
                st.session_state["mun_pagina"] = 1

            col_cfg, col_nav = st.columns([1, 2], gap="large")
            with col_cfg:
                por_pagina = st.selectbox(
                    "Linhas por página",
                    options=[25, 50, 100, 250],
                    index=1,
                    key="mun_por_pagina",
                    on_change=_reset_mun_pagina,
                )
            n_paginas = max(1, -(-n_mun // por_pagina))  # divisão para cima

            # O widget lê a página de session_state (por isso NÃO passamos `value`,
            # que conflita com a `key` e reemite warning a cada rerun). Inicializa
            # uma vez e trava defensivamente no intervalo [1, n_paginas] ANTES de
            # instanciar o widget — garante que max_value nunca seja violado.
            pagina_atual = int(st.session_state.get("mun_pagina", 1))
            st.session_state["mun_pagina"] = min(max(pagina_atual, 1), n_paginas)
            with col_nav:
                pagina = st.number_input(
                    f"Página (1 a {n_paginas})",
                    min_value=1,
                    max_value=n_paginas,
                    step=1,
                    key="mun_pagina",
                )

            ini = (int(pagina) - 1) * por_pagina
            fim = ini + por_pagina
            fatia = tabela.iloc[ini:fim].copy()
            # Formatação BR só na exibição (mantém os tipos numéricos na origem).
            fatia["Beneficiários ativos"] = fatia["qt_beneficiarios_ativos"].map(fmt)
            fatia["Participação"] = fatia["Participação"].map(
                lambda p: f"{p:.2f}%".replace(".", ",")
            )
            fatia = fatia.rename(
                columns={
                    "cd_municipio": "Cód. IBGE",
                    "nm_municipio": "Município",
                }
            )[
                [
                    "Posição",
                    "Cód. IBGE",
                    "Município",
                    "Beneficiários ativos",
                    "Participação",
                ]
            ]

            st.dataframe(fatia, use_container_width=True, hide_index=True)
            st.caption(
                f"Exibindo {fmt(ini + 1)}–{fmt(min(fim, n_mun))} de {fmt(n_mun)} "
                f"municípios · página {int(pagina)} de {n_paginas}."
            )
    else:
        st.info("Sem dados de municípios em `output/`.")

# st.divider()
st.caption(
    "Fonte: Dados Abertos da ANS · Pipeline Medallion (PySpark + Delta Lake + MinIO) · "
    "Dashboard servindo a camada Gold curada."
)

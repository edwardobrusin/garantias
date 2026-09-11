"""
Dashboard — Portafolio de Garantías (NAFIN / BANCOMEXT)
=========================================================
One-pager analítico construido con Streamlit + Plotly, con DuckDB como
motor de agregación sobre un archivo Parquet ya limpio y optimizado.

Requisitos:
    pip install streamlit duckdb pandas plotly

Ejecución:
    streamlit run app.py

Nota de datos:
    Este archivo NO realiza limpieza de datos. Asume que
    `PARQUET_PATH` apunta a un Parquet ya curado con el esquema:

    [Fecha Apertura, Fecha Registro, Nombre Intermediario,
     Bancario/No Bancario, Programa, Estado, Nombre Acreditado,
     RFC Acreditado, Tasa, Banco(Nafin/BCMXT), Monto Inicial,
     Monto Garantizado, Ultimo Saldo, Periodo_Corte, Programa_Limpio,
     Estado_v2]

    Ajusta la constante PARQUET_PATH a la ruta real antes de ejecutar.
"""

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ======================================================================
# 1. CONFIGURACIÓN DE PÁGINA
# ======================================================================
st.set_page_config(
    page_title="Portafolio de Garantías | NAFIN · BANCOMEXT",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Ruta del Parquet optimizado (ajustar a la ubicación real del archivo).
PARQUET_PATH = "data/intermediate/garantias.parquet"

# ----------------------------------------------------------------------
# Paleta corporativa — alineada al config.toml (fondo F8FAFC, acento 2596be)
# ----------------------------------------------------------------------
BG = "#F8FAFC"
PRIMARY = "#2596BE"
PRIMARY_DARK = "#1C7691"
SLATE_100 = "#F1F5F9"
SLATE_200 = "#E2E8F0"
SLATE_500 = "#64748B"
SLATE_700 = "#334155"
SLATE_900 = "#0F172A"

# Secuencia categórica para gráficos con múltiples series (treemap, dona, barras),
# anclada al acento de marca + una escala de grises corporativos como apoyo.
CHART_COLORS = [
    PRIMARY, SLATE_700, "#5CB3D1", "#94A3B8",
    "#0F4C5C", "#8AD1E6", "#CBD5E1", PRIMARY_DARK,
]

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre",
    11: "noviembre", 12: "diciembre",
}


def mes_es(fecha) -> str:
    """Formatea una fecha como 'mes año' en español, sin depender del locale."""
    return f"{MESES_ES[fecha.month]} {fecha.year}"


def fmt_mdp(valor: float) -> str:
    """Formatea un monto en pesos a notación compacta (mdp / mmdp)."""
    if valor is None or pd.isna(valor):
        return "N/D"
    abs_valor = abs(valor)
    if abs_valor >= 1_000_000_000:
        return f"${valor / 1_000_000_000:,.1f} mmdp"
    if abs_valor >= 1_000_000:
        return f"${valor / 1_000_000:,.1f} mdp"
    if abs_valor >= 1_000:
        return f"${valor / 1_000:,.1f} mil"
    return f"${valor:,.0f}"


def fmt_num(valor) -> str:
    """Formatea un conteo entero con separador de miles."""
    if valor is None or pd.isna(valor):
        return "N/D"
    return f"{int(valor):,}"


# ======================================================================
# 2. ESTILOS — Estética Clean & Corporate
# ======================================================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, sans-serif;
}}

/* Chrome nativo de Streamlit fuera — este es un one-pager sin navegación */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header {{ visibility: hidden; }}

.block-container {{
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 1220px;
}}

h1 {{
    font-size: 1.9rem;
    font-weight: 700;
    color: {SLATE_900};
    margin-bottom: 0.15rem;
    letter-spacing: -0.01em;
}}

.subtitulo {{
    color: {SLATE_500};
    font-size: 0.95rem;
    margin-top: 0;
}}

/* Tarjetas de métricas */
[data-testid="stMetric"] {{
    background-color: #FFFFFF;
    border: 1px solid {SLATE_200};
    border-radius: 12px;
    padding: 1.2rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
[data-testid="stMetric"]:hover {{
    transform: translateY(-3px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.05);
    border-color: {PRIMARY};
}}
[data-testid="stMetricLabel"] {{
    color: {SLATE_500};
    font-size: 0.80rem;
    font-weight: 500;
}}
[data-testid="stMetricValue"] {{
    color: {SLATE_900};
    font-size: 1.45rem;
    font-weight: 600;
}}

/* Contenedores con borde (tarjetas de gráficos) */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: #FFFFFF;
    border-radius: 12px;
}}

.chart-title {{
    font-size: 1.0rem;
    font-weight: 600;
    color: {SLATE_900};
    margin: 0 0 0.15rem 0;
}}
.chart-insight {{
    font-size: 0.85rem;
    color: {SLATE_500};
    margin: 0 0 0.7rem 0;
}}

hr {{
    margin: 1.7rem 0;
    border-color: {SLATE_200};
}}
</style>
""", unsafe_allow_html=True)


# ======================================================================
# 3. CAPA DE DATOS (DuckDB sobre Parquet)
# ======================================================================
@st.cache_resource(show_spinner=False)
def get_connection() -> duckdb.DuckDBPyConnection:
    """Conexión DuckDB persistente para la sesión del servidor."""
    con = duckdb.connect(database=":memory:")
    con.execute(f"""
        CREATE OR REPLACE VIEW garantias AS
        SELECT * FROM read_parquet('{PARQUET_PATH}')
    """)
    return con


@st.cache_data(show_spinner=False)
def get_bounds():
    """Rango de fechas y catálogos disponibles para poblar los filtros."""
    con = get_connection()
    fecha_min, fecha_max = con.execute(
        'SELECT MIN("Fecha Apertura"), MAX("Fecha Apertura") FROM garantias'
    ).fetchone()
    bancos = con.execute(
        'SELECT DISTINCT "Banco(Nafin/BCMXT)" FROM garantias ORDER BY 1'
    ).fetchdf().iloc[:, 0].tolist()
    estados = con.execute(
        'SELECT DISTINCT "Estado_v2" FROM garantias ORDER BY 1'
    ).fetchdf().iloc[:, 0].tolist()
    return pd.Timestamp(fecha_min).date(), pd.Timestamp(fecha_max).date(), bancos, estados


def build_where(fecha_ini, fecha_fin, bancos_sel: list, estados_sel: list):
    """Construye la cláusula WHERE parametrizada según los filtros globales.

    Un multiselect vacío se interpreta como 'sin filtro' (incluye todos).
    """
    clausulas = ['"Fecha Apertura" BETWEEN ? AND ?']
    params = [fecha_ini, fecha_fin]

    if bancos_sel:
        marcadores = ",".join(["?"] * len(bancos_sel))
        clausulas.append(f'"Banco(Nafin/BCMXT)" IN ({marcadores})')
        params.extend(bancos_sel)

    if estados_sel:
        marcadores = ",".join(["?"] * len(estados_sel))
        clausulas.append(f'"Estado_v2" IN ({marcadores})')
        params.extend(estados_sel)

    return " AND ".join(clausulas), params


@st.cache_data(show_spinner=False)
def query_kpis(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple) -> pd.Series:
    """KPIs agregados de la Hero Section."""
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT
            SUM("Monto Inicial")                    AS monto_inicial,
            SUM("Monto Garantizado")                AS monto_garantizado,
            SUM("Ultimo Saldo")                      AS saldo_vivo,
            COUNT(DISTINCT "RFC Acreditado")         AS acreditados,
            COUNT(DISTINCT "Nombre Intermediario")   AS intermediarios,
            SUM(TRY_CAST(REPLACE("Tasa", '%', '') AS DOUBLE) * "Monto Inicial") / NULLIF(SUM("Monto Inicial"), 0) AS tasa_ponderada
        FROM garantias
        WHERE {where_sql}
    """
    return con.execute(sql, params).fetchdf().iloc[0]


@st.cache_data(show_spinner=False)
def query_evolucion(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple) -> pd.DataFrame:
    """Colocación mensual (Monto Inicial) según Fecha Apertura."""
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT
            date_trunc('month', "Fecha Apertura") AS mes,
            SUM("Monto Inicial")                  AS colocacion
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY 1
    """
    return con.execute(sql, params).fetchdf()


@st.cache_data(show_spinner=False)
def query_treemap(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple) -> pd.DataFrame:
    """Monto garantizado por Banco -> Programa Limpio, para el treemap jerárquico."""
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT
            "Banco(Nafin/BCMXT)"     AS banco,
            "Programa_Limpio"        AS programa,
            SUM("Monto Garantizado") AS monto
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1, 2
        HAVING SUM("Monto Garantizado") > 0
        ORDER BY monto DESC
    """
    return con.execute(sql, params).fetchdf()


@st.cache_data(show_spinner=False)
def query_geografico(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple) -> pd.DataFrame:
    """Top 10 estados por saldo vivo."""
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT "Estado_v2" AS estado, SUM("Ultimo Saldo") AS saldo
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY saldo DESC
        LIMIT 10
    """
    return con.execute(sql, params).fetchdf()


@st.cache_data(show_spinner=False)
def query_intermediarios(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple) -> pd.DataFrame:
    """Saldo vivo por intermediario financiero, para el market share."""
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT "Nombre Intermediario" AS intermediario, SUM("Ultimo Saldo") AS saldo
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY saldo DESC
    """
    return con.execute(sql, params).fetchdf()


def aplicar_tema(fig: go.Figure, altura: int = 380) -> go.Figure:
    """Aplica el tema visual corporativo a cualquier figura de Plotly."""
    fig.update_layout(
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="Inter, sans-serif", color=SLATE_900, size=13),
        margin=dict(l=8, r=8, t=8, b=8),
        height=altura,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12, font_family="Inter, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=SLATE_200, zeroline=False)
    return fig


# ======================================================================
# 4. HERO SECTION + BARRA DE CONTROL (filtros globales)
# ======================================================================
fecha_min, fecha_max, bancos_disponibles, estados_disponibles = get_bounds()

col_titulo, col_filtros = st.columns([5, 1.3])

with col_titulo:
    st.markdown("<h1>Portafolio de Garantías</h1>", unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitulo">Consolidado NAFIN · BANCOMEXT — programas de fomento y segundo piso</p>',
        unsafe_allow_html=True,
    )

with col_filtros:
    st.write("")  # alineación vertical con el título
    with st.popover("🔍  Filtros", width="stretch"):
        st.markdown("**Periodo (Fecha Apertura)**")
        rango_fechas = st.date_input(
            "Periodo",
            value=(fecha_min, fecha_max),
            min_value=fecha_min,
            max_value=fecha_max,
            key="filtro_fechas",
            label_visibility="collapsed",
        )
        st.markdown("**Banco de 2° piso**")
        bancos_sel = st.multiselect(
            "Banco",
            options=bancos_disponibles,
            default=[],
            placeholder="Todos los bancos",
            key="filtro_bancos",
            label_visibility="collapsed",
        )
        st.markdown("**Estado**")
        estados_sel = st.multiselect(
            "Estado",
            options=estados_disponibles,
            default=[],
            placeholder="Todos los estados",
            key="filtro_estados",
            label_visibility="collapsed",
        )

# El date_input en modo rango puede devolver un solo elemento mientras
# el usuario está seleccionando; se sostiene el rango completo por defecto.
if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
    fecha_ini, fecha_fin = rango_fechas
else:
    fecha_ini, fecha_fin = fecha_min, fecha_max

filtros_bancos = tuple(bancos_sel)
filtros_estados = tuple(estados_sel)

# ----------------------------------------------------------------------
# Métricas de alto impacto
# ----------------------------------------------------------------------
kpis = query_kpis(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

pct_amortizado = 0.0
if kpis["monto_inicial"] and kpis["monto_inicial"] > 0:
    pct_amortizado = (1 - kpis["saldo_vivo"] / kpis["monto_inicial"]) * 100

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    with st.container(border=True):
        st.metric("Monto Inicial Colocado", fmt_mdp(kpis["monto_inicial"]))
with c2:
    with st.container(border=True):
        st.metric("Monto Garantizado", fmt_mdp(kpis["monto_garantizado"]))
with c3:
    with st.container(border=True):
        st.metric(
            "Saldo Vivo Actual",
            fmt_mdp(kpis["saldo_vivo"]),
            delta=f"{pct_amortizado:.1f}% amortizado",
        )
with c4:
    with st.container(border=True):
        st.metric("Acreditados Únicos", fmt_num(kpis["acreditados"]))
with c5:
    with st.container(border=True):
        st.metric("Tasa Ponderada", f"{kpis['tasa_ponderada']:.2f}%")

st.divider()

# ======================================================================
# 5. VISUALIZACIONES CORE
# ======================================================================

# ---- 5.1 Evolución temporal (colocación mensual) ----------------------
with st.container(border=True):
    st.markdown('<p class="chart-title">Evolución mensual de la colocación</p>', unsafe_allow_html=True)
    df_evol = query_evolucion(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

    if df_evol.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        pico = df_evol.loc[df_evol["colocacion"].idxmax()]
        st.markdown(
            f'<p class="chart-insight">El mes con mayor colocación fue '
            f'{mes_es(pico["mes"])}, con {fmt_mdp(pico["colocacion"])}.</p>',
            unsafe_allow_html=True,
        )
        fig_evol = go.Figure(go.Scatter(
            x=df_evol["mes"], y=df_evol["colocacion"],
            mode="lines",
            line=dict(color=PRIMARY, width=2.5, shape="spline", smoothing=0.5),
            fill="tozeroy", fillcolor="rgba(37, 150, 190, 0.12)",
            hovertemplate="%{x|%b %Y}<br>Colocación: $%{y:,.0f}<extra></extra>",
        ))
        aplicar_tema(fig_evol, altura=320)
        fig_evol.update_yaxes(tickprefix="$", tickformat=".2s")
        st.plotly_chart(fig_evol, width="stretch", config={"displayModeBar": False})

# ---- 5.2 Distribución de portafolio (treemap) + Intermediarios (dona) --
col_tree, col_donut = st.columns([2, 1])

with col_tree:
    with st.container(border=True):
        st.markdown('<p class="chart-title">Distribución del portafolio por banco y programa</p>', unsafe_allow_html=True)
        df_tree = query_treemap(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

        if df_tree.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            top_prog = df_tree.loc[df_tree["monto"].idxmax()]
            participacion = top_prog["monto"] / df_tree["monto"].sum() * 100
            st.markdown(
                f'<p class="chart-insight">{top_prog["programa"]} ({top_prog["banco"]}) concentra el '
                f'{participacion:.1f}% del monto garantizado mostrado.</p>',
                unsafe_allow_html=True,
            )
            fig_tree = px.treemap(
                df_tree,
                path=[px.Constant("Portafolio"), "banco", "programa"],
                values="monto",
                color="banco",
                color_discrete_map={"NAFIN": PRIMARY, "BANCOMEXT": SLATE_700},
            )
            fig_tree.update_traces(
                texttemplate="<b>%{label}</b><br>$%{value:,.2s}",
                hovertemplate="%{label}<br>Monto Garantizado: $%{value:,.0f}<extra></extra>",
                marker=dict(line=dict(width=1.5, color=BG)),
                root_color=SLATE_100,
            )
            aplicar_tema(fig_tree, altura=380)
            fig_tree.update_layout(margin=dict(l=4, r=4, t=4, b=4))
            st.plotly_chart(fig_tree, width="stretch", config={"displayModeBar": False})

with col_donut:
    with st.container(border=True):
        st.markdown('<p class="chart-title">Composición por intermediario</p>', unsafe_allow_html=True)
        df_inter = query_intermediarios(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

        if df_inter.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            # Se agrupan los intermediarios menores a "Otros" para no saturar la leyenda.
            TOP_N = 7
            df_inter = df_inter.sort_values("saldo", ascending=False).reset_index(drop=True)
            if len(df_inter) > TOP_N:
                df_plot = df_inter.iloc[:TOP_N].copy()
                otros = df_inter.iloc[TOP_N:]["saldo"].sum()
                df_plot.loc[len(df_plot)] = ["Otros intermediarios", otros]
            else:
                df_plot = df_inter

            lider = df_inter.iloc[0]
            participacion_lider = lider["saldo"] / df_inter["saldo"].sum() * 100
            st.markdown(
                f'<p class="chart-insight">{lider["intermediario"]} concentra el '
                f'{participacion_lider:.1f}% del saldo vivo.</p>',
                unsafe_allow_html=True,
            )
            fig_donut = px.pie(
                df_plot, names="intermediario", values="saldo",
                hole=0.6, color_discrete_sequence=CHART_COLORS,
            )
            fig_donut.update_traces(
                textposition="outside", textinfo="percent",
                hovertemplate="%{label}<br>Saldo: $%{value:,.0f} (%{percent})<extra></extra>",
            )
            aplicar_tema(fig_donut, altura=380)
            fig_donut.update_layout(
                showlegend=True,
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0, font=dict(size=10)),
                margin=dict(l=4, r=4, t=4, b=4),
            )
            st.plotly_chart(fig_donut, width="stretch", config={"displayModeBar": False})

# ---- 5.3 Rendimiento geográfico (top 10 estados) -----------------------
with st.container(border=True):
    st.markdown('<p class="chart-title">Top 10 estados por saldo vivo</p>', unsafe_allow_html=True)
    df_geo = query_geografico(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

    if df_geo.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        df_geo = df_geo.sort_values("saldo", ascending=True)  # el mayor queda arriba en la barra horizontal
        lider_estado = df_geo.iloc[-1]
        st.markdown(
            f'<p class="chart-insight">{lider_estado["estado"]} encabeza el portafolio con '
            f'{fmt_mdp(lider_estado["saldo"])} en saldo vivo.</p>',
            unsafe_allow_html=True,
        )
        fig_geo = px.bar(
            df_geo, x="saldo", y="estado", orientation="h",
            color="saldo", color_continuous_scale=[SLATE_200, PRIMARY],
            text=df_geo["saldo"].apply(fmt_mdp),
        )
        fig_geo.update_traces(
            textposition="outside",
            hovertemplate="%{y}<br>Saldo: $%{x:,.0f}<extra></extra>",
        )
        fig_geo.update_coloraxes(showscale=False)
        aplicar_tema(fig_geo, altura=420)
        fig_geo.update_xaxes(tickprefix="$", tickformat=".2s", title=None)
        fig_geo.update_yaxes(title=None)
        st.plotly_chart(fig_geo, width="stretch", config={"displayModeBar": False})

# ======================================================================
# 6. PIE DE PÁGINA
# ======================================================================
st.caption(
    f"Datos filtrados del {fecha_ini:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} · "
    f"{fmt_num(kpis['intermediarios'])} intermediarios activos en la selección."
)
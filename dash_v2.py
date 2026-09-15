import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Portafolio de Garantías | NAFIN · BANCOMEXT",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PARQUET_PATH = "data/intermediate/garantias.parquet"

BG = "#F8FAFC"
PRIMARY = "#2596BE"
PRIMARY_DARK = "#1C7691"
SLATE_100 = "#F1F5F9"
SLATE_200 = "#E2E8F0"
SLATE_500 = "#64748B"
SLATE_700 = "#334155"
SLATE_900 = "#0F172A"

CHART_COLORS = [
    PRIMARY, SLATE_700, "#5CB3D1", "#94A3B8",
    "#0F4C5C", "#8AD1E6", "#CBD5E1", PRIMARY_DARK,
]

PALETTE_NAFIN = [
    "#2596BE", "#5CB3D1", "#8AD1E6", "#1C7691",
    "#0F4C5C", "#CBD5E1", "#94A3B8",
]

PALETTE_BCMXT = [
    "#334155", "#475569", "#64748B", "#94A3B8",
    "#CBD5E1", "#1E293B", "#0F172A",
]

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre",
    11: "noviembre", 12: "diciembre",
}

NAME_NORMALIZER = {
    "Coahuila de Zaragoza": "Coahuila",
    "Michoacán de Ocampo": "Michoacán",
    "Veracruz de Ignacio de la Llave": "Veracruz",
    "Estado de México": "México",
    "Mexico": "México",
    "Distrito Federal": "Ciudad de México",
    "CDMX": "Ciudad de México",
}

def fmt_mdp(valor: float) -> str:
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
    if valor is None or pd.isna(valor):
        return "N/D"
    return f"{int(valor):,}"

def fmt_periodo(fecha, gran: str) -> str:
    if pd.isna(fecha):
        return "N/D"
    ts = pd.Timestamp(fecha)
    if gran == "Día":
        return f"{ts.day} {MESES_ES.get(ts.month, '')[:3]} {ts.year}"
    elif gran == "Semana":
        return f"Sem {ts.isocalendar()} ({ts.day} {MESES_ES.get(ts.month, '')[:3]} {ts.year})"
    elif gran == "Quincena":
        q = "1ª Qna" if ts.day <= 15 else "2ª Qna"
        return f"{q} {MESES_ES.get(ts.month, '')[:3]} {ts.year}"
    elif gran == "Mes":
        return f"{MESES_ES.get(ts.month, '')} {ts.year}"
    elif gran == "Trimestre":
        return f"T{ts.quarter} {ts.year}"
    elif gran == "Semestre":
        s = "1S" if ts.month <= 6 else "2S"
        return f"{s} {ts.year}"
    elif gran == "Año":
        return f"{ts.year}"
    return str(fecha)

def aplicar_tema(fig: go.Figure, altura: int = 380) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="Inter, sans-serif", color=SLATE_900, size=12),
        margin=dict(l=10, r=10, t=10, b=10),
        height=altura,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="#0F172A", font_size=12, font_family="Inter, sans-serif", font_color="#F8FAFC"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=SLATE_200, zeroline=False)
    return fig

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, sans-serif;
}}

.stApp {{
    background-color: {BG};
}}

#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header {{ visibility: hidden; }}

.block-container {{
    padding-top: 1.6rem;
    padding-bottom: 3rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}}

h1 {{
    font-size: 2.1rem;
    font-weight: 800;
    color: {SLATE_900};
    margin-bottom: 0.15rem;
    letter-spacing: -0.02em;
}}

.subtitulo {{
    color: {SLATE_500};
    font-size: 0.95rem;
    margin-top: 0;
    margin-bottom: 1.2rem;
}}

.metric-card {{
    background-color: #FFFFFF;
    border: 1px solid {SLATE_200};
    border-radius: 12px;
    padding: 1.2rem 1.3rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03), 0 2px 4px -2px rgba(0, 0, 0, 0.03);
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}

.metric-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.06);
    border-color: {PRIMARY};
}}

.metric-label {{
    color: {SLATE_500};
    font-size: 0.80rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 0.3rem;
}}

.metric-val {{
    color: {SLATE_900};
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    line-height: 1.2;
}}

.metric-badge {{
    display: inline-block;
    align-self: flex-start;
    margin-top: 0.4rem;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    background-color: #ECFDF5;
    color: #059669;
}}

.metric-sub {{
    color: {SLATE_500};
    font-size: 0.80rem;
    margin-top: 0.4rem;
}}

div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: #FFFFFF;
    border: 1px solid {SLATE_200};
    border-radius: 12px;
    box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02);
}}

.stButton > button {{
    border-radius: 8px;
    font-size: 0.80rem;
    font-weight: 600;
    padding: 0.35rem 0.6rem;
    transition: all 0.2s ease-in-out;
    border: 1px solid {SLATE_200};
    background-color: #FFFFFF;
    color: {SLATE_700};
}}

.stButton > button:hover {{
    border-color: {PRIMARY};
    color: {PRIMARY};
    background-color: {SLATE_100};
}}

.chart-title {{
    font-size: 1.05rem;
    font-weight: 700;
    color: {SLATE_900};
    margin: 0 0 0.15rem 0;
    letter-spacing: -0.01em;
}}

.chart-insight {{
    font-size: 0.85rem;
    color: {SLATE_500};
    margin: 0 0 0.75rem 0;
}}

hr {{
    margin: 1.5rem 0;
    border-color: {SLATE_200};
}}
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def get_connection() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    con.execute(f"""
        CREATE OR REPLACE VIEW garantias AS
        SELECT * FROM read_parquet('{PARQUET_PATH}')
    """)
    return con

@st.cache_data(show_spinner=False)
def get_bounds():
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
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT
            SUM("Monto Inicial")                  AS monto_inicial,
            SUM("Monto Garantizado")              AS monto_garantizado,
            SUM("Ultimo Saldo")                    AS saldo_vivo,
            COUNT(DISTINCT "RFC Acreditado")       AS acreditados,
            COUNT(DISTINCT "Nombre Intermediario") AS intermediarios
        FROM garantias
        WHERE {where_sql}
    """
    return con.execute(sql, params).fetchdf().iloc[0]

@st.cache_data(show_spinner=False)
def query_evolucion(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple, gran: str) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    if gran == "Día":
        sql_date = 'CAST("Fecha Apertura" AS DATE)'
    elif gran == "Semana":
        sql_date = 'date_trunc(\'week\', "Fecha Apertura")'
    elif gran == "Quincena":
        sql_date = """CASE
            WHEN DAY(CAST("Fecha Apertura" AS DATE)) <= 15
            THEN CAST(STRFTIME(CAST("Fecha Apertura" AS DATE), '%Y-%m-01') AS DATE)
            ELSE CAST(STRFTIME(CAST("Fecha Apertura" AS DATE), '%Y-%m-16') AS DATE)
        END"""
    elif gran == "Mes":
        sql_date = 'date_trunc(\'month\', "Fecha Apertura")'
    elif gran == "Trimestre":
        sql_date = 'date_trunc(\'quarter\', "Fecha Apertura")'
    elif gran == "Semestre":
        sql_date = """CASE
            WHEN MONTH(CAST("Fecha Apertura" AS DATE)) <= 6
            THEN CAST(STRFTIME(CAST("Fecha Apertura" AS DATE), '%Y-01-01') AS DATE)
            ELSE CAST(STRFTIME(CAST("Fecha Apertura" AS DATE), '%Y-07-01') AS DATE)
        END"""
    elif gran == "Año":
        sql_date = 'date_trunc(\'year\', "Fecha Apertura")'
    else:
        sql_date = 'date_trunc(\'month\', "Fecha Apertura")'
    sql = f"""
        SELECT
            {sql_date} AS periodo,
            SUM("Monto Inicial") AS colocacion
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY 1
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_programas_distribucion(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT
            "Programa_Limpio"        AS programa,
            SUM("Monto Garantizado") AS monto
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM("Monto Garantizado") > 0
        ORDER BY monto DESC
        LIMIT 10
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_mapa(fecha_ini, fecha_fin, bancos_sel: tuple, estados_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, list(bancos_sel), list(estados_sel))
    sql = f"""
        SELECT
            "Estado_v2"                      AS estado,
            SUM("Ultimo Saldo")              AS saldo,
            SUM("Monto Garantizado")         AS monto_garantizado,
            COUNT(DISTINCT "RFC Acreditado") AS acreditados
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM("Ultimo Saldo") > 0
        ORDER BY saldo DESC
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_intermediarios_banco(fecha_ini, fecha_fin, banco: str, estados_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, [banco], list(estados_sel))
    sql = f"""
        SELECT
            "Nombre Intermediario" AS intermediario,
            SUM("Ultimo Saldo")    AS saldo
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM("Ultimo Saldo") > 0
        ORDER BY saldo DESC
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_programas_banco(fecha_ini, fecha_fin, banco: str, estados_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where(fecha_ini, fecha_fin, [banco], list(estados_sel))
    sql = f"""
        SELECT
            "Programa_Limpio"        AS programa,
            SUM("Ultimo Saldo")      AS saldo,
            SUM("Monto Garantizado") AS monto_garantizado
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM("Ultimo Saldo") > 0
        ORDER BY saldo DESC
        LIMIT 8
    """
    return con.execute(sql, params).fetchdf()

def render_donut_chart(df_data: pd.DataFrame, banco_nombre: str, palette: list):
    if df_data.empty:
        return None
    TOP_N = 6
    df_sorted = df_data.sort_values("saldo", ascending=False).reset_index(drop=True)
    if len(df_sorted) > TOP_N:
        df_plot = df_sorted.iloc[:TOP_N].copy()
        otros_val = df_sorted.iloc[TOP_N:]["saldo"].sum()
        df_plot.loc[len(df_plot)] = ["Otros intermediarios", otros_val]
    else:
        df_plot = df_sorted
    fig = px.pie(
        df_plot,
        names="intermediario",
        values="saldo",
        hole=0.6,
        color_discrete_sequence=palette,
    )
    fig.update_traces(
        textposition="outside",
        textinfo="percent",
        hovertemplate="%{label}<br>Saldo: $%{value:,.0f} (%{percent})<extra></extra>",
    )
    aplicar_tema(fig, altura=380)
    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.08,
            xanchor="center",
            x=0.5,
            font=dict(size=10),
        ),
        margin=dict(l=8, r=8, t=8, b=30),
    )
    return fig

def render_column_chart(df_data: pd.DataFrame, banco_nombre: str):
    if df_data.empty:
        return None
    scale_colors = [SLATE_200, PRIMARY] if banco_nombre == "NAFIN" else [SLATE_200, SLATE_700]
    df_plot = df_data.head(8)
    fig = px.bar(
        df_plot,
        x="intermediario",
        y="saldo",
        color="saldo",
        color_continuous_scale=scale_colors,
        text=df_plot["saldo"].apply(fmt_mdp),
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Saldo: $%{y:,.0f}<extra></extra>",
    )
    fig.update_coloraxes(showscale=False)
    aplicar_tema(fig, altura=380)
    fig.update_xaxes(title=None, tickangle=-20, tickfont=dict(size=10))
    fig.update_yaxes(tickprefix="$", tickformat=".2s", title=None)
    fig.update_layout(margin=dict(l=8, r=8, t=15, b=30))
    return fig

fecha_min, fecha_max, bancos_disponibles, estados_disponibles = get_bounds()

if "filtro_rango_fechas" not in st.session_state:
    st.session_state["filtro_rango_fechas"] = (fecha_min, fecha_max)
if "filtro_bancos" not in st.session_state:
    st.session_state["filtro_bancos"] = []
if "filtro_estados" not in st.session_state:
    st.session_state["filtro_estados"] = []
if "preset_selector" not in st.session_state:
    st.session_state["preset_selector"] = "Histórico"

def apply_preset():
    preset = st.session_state["preset_selector"]
    if preset == "YTD":
        st.session_state["filtro_rango_fechas"] = (pd.Timestamp(fecha_max.year, 1, 1).date(), fecha_max)
    elif preset == "Últimos 6M":
        f_calc = (pd.Timestamp(fecha_max) - pd.DateOffset(months=6)).date()
        st.session_state["filtro_rango_fechas"] = (max(fecha_min, f_calc), fecha_max)
    elif preset == "Último Año":
        f_calc = (pd.Timestamp(fecha_max) - pd.DateOffset(years=1)).date()
        st.session_state["filtro_rango_fechas"] = (max(fecha_min, f_calc), fecha_max)
    elif preset == "Histórico":
        st.session_state["filtro_rango_fechas"] = (fecha_min, fecha_max)

def reset_all_filters():
    st.session_state["filtro_rango_fechas"] = (fecha_min, fecha_max)
    st.session_state["filtro_bancos"] = []
    st.session_state["filtro_estados"] = []
    st.session_state["preset_selector"] = "Histórico"

st.markdown("<h1>Portafolio de Garantías</h1>", unsafe_allow_html=True)
st.markdown(
    '<p class="subtitulo">Consolidado NAFIN · BANCOMEXT — programas de fomento y financiamiento de segundo piso</p>',
    unsafe_allow_html=True,
)

with st.container(border=True):
    fc1, fc2, fc3, fc4, fc5 = st.columns([1.0, 1.3, 1.2, 1.2, 0.4])
    with fc1:
        st.markdown("**Atajos de Periodo**")
        st.selectbox(
            "Atajos de Periodo",
            options=["Histórico", "YTD", "Últimos 6M", "Último Año"],
            key="preset_selector",
            label_visibility="collapsed",
            on_change=apply_preset
        )
    with fc2:
        st.markdown("**Periodo (Fecha)**")
        rango_fechas = st.date_input(
            "Periodo",
            min_value=fecha_min,
            max_value=fecha_max,
            key="filtro_rango_fechas",
            label_visibility="collapsed",
        )
    with fc3:
        st.markdown("**Banco de 2° piso**")
        bancos_sel = st.multiselect(
            "Banco",
            options=bancos_disponibles,
            placeholder="Todos los bancos",
            key="filtro_bancos",
            label_visibility="collapsed",
        )
    with fc4:
        st.markdown("**Entidad Federativa**")
        estados_sel = st.multiselect(
            "Estado",
            options=estados_disponibles,
            placeholder="Todos los estados",
            key="filtro_estados",
            label_visibility="collapsed",
        )
    with fc5:
        st.markdown("**&nbsp;**")
        st.button("🔄", on_click=reset_all_filters, use_container_width=True, help="Restablecer Filtros")

if isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 2:
    fecha_ini, fecha_fin = rango_fechas
elif isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 1:
    fecha_ini, fecha_fin = rango_fechas[0], fecha_max
else:
    fecha_ini, fecha_fin = fecha_min, fecha_max

filtros_bancos = tuple(bancos_sel)
filtros_estados = tuple(estados_sel)

kpis = query_kpis(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

pct_amortizado = 0.0
if kpis["monto_inicial"] and kpis["monto_inicial"] > 0:
    pct_amortizado = (1 - kpis["saldo_vivo"] / kpis["monto_inicial"]) * 100

st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Monto Inicial Colocado</div>
        <div class="metric-val">{fmt_mdp(kpis["monto_inicial"])}</div>
        <div class="metric-sub">Total de financiamiento colocado</div>
    </div>
    """, unsafe_allow_html=True)
with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Monto Garantizado</div>
        <div class="metric-val">{fmt_mdp(kpis["monto_garantizado"])}</div>
        <div class="metric-sub">Cobertura de riesgo institucional</div>
    </div>
    """, unsafe_allow_html=True)
with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Saldo Vivo Actual</div>
        <div class="metric-val">{fmt_mdp(kpis["saldo_vivo"])}</div>
        <div class="metric-badge">▲ {pct_amortizado:.1f}% amortizado</div>
    </div>
    """, unsafe_allow_html=True)
with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Acreditados Únicos</div>
        <div class="metric-val">{fmt_num(kpis["acreditados"])}</div>
        <div class="metric-sub">Empresas y beneficiarios activos</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

with st.container(border=True):
    col_hdr1, col_hdr2 = st.columns([3.5, 1.2])
    with col_hdr1:
        st.markdown('<p class="chart-title">Evolución temporal de la colocación</p>', unsafe_allow_html=True)
    with col_hdr2:
        gran_sel = st.selectbox(
            "Agrupación",
            options=["Día", "Semana", "Quincena", "Mes", "Trimestre", "Semestre", "Año"],
            index=3,
            key="gran_selector",
            label_visibility="collapsed",
        )
    df_evol = query_evolucion(fecha_ini, fecha_fin, filtros_bancos, filtros_estados, gran_sel)
    if df_evol.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        pico = df_evol.loc[df_evol["colocacion"].idxmax()]
        pico_str = fmt_periodo(pico["periodo"], gran_sel)
        st.markdown(
            f'<p class="chart-insight">El periodo con mayor colocación fue <b>{pico_str}</b>, con <b>{fmt_mdp(pico["colocacion"])}</b>.</p>',
            unsafe_allow_html=True,
        )
        df_evol["hover_label"] = df_evol["periodo"].apply(lambda x: fmt_periodo(x, gran_sel))
        fig_evol = go.Figure(go.Bar(
            x=df_evol["periodo"],
            y=df_evol["colocacion"],
            customdata=df_evol["hover_label"],
            marker=dict(color=PRIMARY),
            hovertemplate="<b>%{customdata}</b><br>Colocación: $%{y:,.0f}<extra></extra>",
        ))
        aplicar_tema(fig_evol, altura=330)
        fig_evol.update_yaxes(tickprefix="$", tickformat=".2s")
        st.plotly_chart(fig_evol, use_container_width=True, config={"displayModeBar": False})

with st.container(border=True):
    st.markdown('<p class="chart-title">Distribución del portafolio por programa (Top 10)</p>', unsafe_allow_html=True)
    df_prog = query_programas_distribucion(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)
    if df_prog.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        df_prog = df_prog.sort_values("monto", ascending=True)
        top_prog = df_prog.iloc[-1]
        part_prog = (top_prog["monto"] / df_prog["monto"].sum()) * 100
        st.markdown(
            f'<p class="chart-insight"><b>{top_prog["programa"]}</b> lidera con <b>{fmt_mdp(top_prog["monto"])}</b> en monto garantizado ({part_prog:.1f}% del top 10 mostrado).</p>',
            unsafe_allow_html=True,
        )
        fig_prog = px.bar(
            df_prog,
            x="monto",
            y="programa",
            orientation="h",
            color="monto",
            color_continuous_scale=[SLATE_200, PRIMARY],
            text=df_prog["monto"].apply(fmt_mdp),
        )
        fig_prog.update_traces(
            textposition="outside",
            hovertemplate="%{y}<br>Monto Garantizado: $%{x:,.0f}<extra></extra>",
        )
        fig_prog.update_coloraxes(showscale=False)
        aplicar_tema(fig_prog, altura=400)
        fig_prog.update_xaxes(tickprefix="$", tickformat=".2s", title=None)
        fig_prog.update_yaxes(title=None)
        st.plotly_chart(fig_prog, use_container_width=True, config={"displayModeBar": False})

col_bank1, col_bank2 = st.columns(2)

if len(filtros_bancos) == 1:
    banco_solo = filtros_bancos[0]
    paleta_activa = PALETTE_NAFIN if banco_solo == "NAFIN" else PALETTE_BCMXT
    with col_bank1:
        with st.container(border=True):
            st.markdown(f'<p class="chart-title">Intermediarios Financieros — {banco_solo}</p>', unsafe_allow_html=True)
            df_inter_solo = query_intermediarios_banco(fecha_ini, fecha_fin, banco_solo, filtros_estados)
            if df_inter_solo.empty:
                st.info(f"No hay intermediarios con saldo activo para {banco_solo}.")
            else:
                top_int = df_inter_solo.iloc[0]
                part_int = (top_int["saldo"] / df_inter_solo["saldo"].sum()) * 100
                st.markdown(
                    f'<p class="chart-insight"><b>{top_int["intermediario"]}</b> lidera con el <b>{part_int:.1f}%</b> del saldo vivo en {banco_solo}.</p>',
                    unsafe_allow_html=True,
                )
                fig_donut_solo = render_donut_chart(df_inter_solo, banco_solo, paleta_activa)
                if fig_donut_solo:
                    st.plotly_chart(fig_donut_solo, use_container_width=True, config={"displayModeBar": False})
    with col_bank2:
        with st.container(border=True):
            st.markdown(f'<p class="chart-title">Top Intermediarios — {banco_solo}</p>', unsafe_allow_html=True)
            if df_inter_solo.empty:
                st.info(f"No hay intermediarios registrados para {banco_solo}.")
            else:
                top_pb = df_inter_solo.iloc[0]
                part_pb = (top_pb["saldo"] / df_inter_solo["saldo"].sum()) * 100
                st.markdown(
                    f'<p class="chart-insight"><b>{top_pb["intermediario"]}</b> representa el <b>{part_pb:.1f}%</b> del saldo en {banco_solo}.</p>',
                    unsafe_allow_html=True,
                )
                fig_col_banco = render_column_chart(df_inter_solo, banco_solo)
                if fig_col_banco:
                    st.plotly_chart(fig_col_banco, use_container_width=True, config={"displayModeBar": False})
else:
    with col_bank1:
        with st.container(border=True):
            st.markdown('<p class="chart-title">Intermediarios Financieros — NAFIN</p>', unsafe_allow_html=True)
            df_inter_nafin = query_intermediarios_banco(fecha_ini, fecha_fin, "NAFIN", filtros_estados)
            if df_inter_nafin.empty:
                st.info("No hay intermediarios activos para NAFIN.")
            else:
                top_naf = df_inter_nafin.iloc[0]
                part_naf = (top_naf["saldo"] / df_inter_nafin["saldo"].sum()) * 100
                st.markdown(
                    f'<p class="chart-insight"><b>{top_naf["intermediario"]}</b> lidera NAFIN con el <b>{part_naf:.1f}%</b> del saldo vivo.</p>',
                    unsafe_allow_html=True,
                )
                fig_donut_naf = render_donut_chart(df_inter_nafin, "NAFIN", PALETTE_NAFIN)
                if fig_donut_naf:
                    st.plotly_chart(fig_donut_naf, use_container_width=True, config={"displayModeBar": False})
    with col_bank2:
        with st.container(border=True):
            st.markdown('<p class="chart-title">Intermediarios Financieros — BANCOMEXT</p>', unsafe_allow_html=True)
            df_inter_bcmxt = query_intermediarios_banco(fecha_ini, fecha_fin, "BANCOMEXT", filtros_estados)
            if df_inter_bcmxt.empty:
                st.info("No hay intermediarios activos para BANCOMEXT.")
            else:
                top_bc = df_inter_bcmxt.iloc[0]
                part_bc = (top_bc["saldo"] / df_inter_bcmxt["saldo"].sum()) * 100
                st.markdown(
                    f'<p class="chart-insight"><b>{top_bc["intermediario"]}</b> lidera BANCOMEXT con el <b>{part_bc:.1f}%</b> del saldo vivo.</p>',
                    unsafe_allow_html=True,
                )
                fig_donut_bc = render_donut_chart(df_inter_bcmxt, "BANCOMEXT", PALETTE_BCMXT)
                if fig_donut_bc:
                    st.plotly_chart(fig_donut_bc, use_container_width=True, config={"displayModeBar": False})

df_mapa = query_mapa(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

with st.container(border=True):
    st.markdown('<p class="chart-title">Distribución territorial de saldo vivo por estado</p>', unsafe_allow_html=True)
    if df_mapa.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        df_mapa_plot = df_mapa.copy()
        
        # Mapeo específico para coincidir con las llaves del GeoJSON
        GEOJSON_MAPPER = {
            "Coahuila": "Coahuila de Zaragoza",
            "Michoacán": "Michoacán de Ocampo",
            "Veracruz": "Veracruz de Ignacio de la Llave",
            "Ciudad de México": "Distrito Federal",
            "CDMX": "Distrito Federal"
        }
        df_mapa_plot["estado_geo"] = df_mapa_plot["estado"].replace(GEOJSON_MAPPER)
        
        url_geojson = "https://raw.githubusercontent.com/angelnmara/geojson/master/mexicoHigh.json"
        
        # Descarga segura del GeoJSON a memoria para evitar bloqueos
        import urllib.request
        import json
        try:
            req = urllib.request.Request(url_geojson, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                geojson_data = json.loads(response.read().decode())
        except Exception:
            geojson_data = url_geojson

        fig_mapa = px.choropleth(
            df_mapa_plot,
            geojson=geojson_data,
            locations="estado_geo",
            featureidkey="properties.name",
            color="saldo",
            color_continuous_scale="Teal",
            hover_name="estado",
        )
        fig_mapa.update_traces(
            customdata=df_mapa_plot[["monto_garantizado", "acreditados"]],
            hovertemplate="<b>%{hovertext}</b><br><span style='color:#7dd3c8; font-weight:700;'>Saldo Vivo:</span> $%{z:,.0f}<br><span style='color:#7dd3c8; font-weight:700;'>Monto Garantizado:</span> $%{customdata[0]:,.0f}<br><span style='color:#7dd3c8; font-weight:700;'>Acreditados:</span> %{customdata:,}<extra></extra>",
            marker_line_color="white",
            marker_line_width=1.5,
            hoverlabel=dict(
                bgcolor="#0F172A",
                font_size=13,
                font_family="Inter, sans-serif",
                font_color="#F8FAFC",
                bordercolor="#0F172A",
                align="left",
            ),
        )
        fig_mapa.update_geos(fitbounds="locations", visible=False, bgcolor="#F8FAFC")
        fig_mapa.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0, "pad": 0},
            height=430,
            autosize=True,
            dragmode=False,
            plot_bgcolor="#F8FAFC",
            paper_bgcolor="#F8FAFC",
            coloraxis_colorbar=dict(
                title="",
                thickness=10,
                len=0.88,
                y=0.5,
                yanchor="middle",
                outlinewidth=0,
                tickfont=dict(color="#64748B"),
                tickprefix="$",
                tickformat=".2s",
            ),
        )
        st.plotly_chart(fig_mapa, use_container_width=True, config={"displayModeBar": False})

with st.container(border=True):
    st.markdown('<p class="chart-title">Top 10 estados por saldo vivo</p>', unsafe_allow_html=True)
    if df_mapa.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        df_geo = df_mapa.head(10).sort_values("saldo", ascending=True)
        lider_estado = df_geo.iloc[-1]
        st.markdown(
            f'<p class="chart-insight"><b>{lider_estado["estado"]}</b> encabeza el portafolio con <b>{fmt_mdp(lider_estado["saldo"])}</b> en saldo vivo.</p>',
            unsafe_allow_html=True,
        )
        fig_geo = px.bar(
            df_geo,
            x="saldo",
            y="estado",
            orientation="h",
            color="saldo",
            color_continuous_scale=[SLATE_200, PRIMARY],
            text=df_geo["saldo"].apply(fmt_mdp),
        )
        fig_geo.update_traces(
            textposition="outside",
            hovertemplate="%{y}<br>Saldo: $%{x:,.0f}<extra></extra>",
        )
        fig_geo.update_coloraxes(showscale=False)
        aplicar_tema(fig_geo, altura=400)
        fig_geo.update_xaxes(tickprefix="$", tickformat=".2s", title=None)
        fig_geo.update_yaxes(title=None)
        st.plotly_chart(fig_geo, use_container_width=True, config={"displayModeBar": False})

st.caption(
    f"Datos filtrados del {fecha_ini:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} · "
    f"{fmt_num(kpis['intermediarios'])} intermediarios activos en la selección."
)
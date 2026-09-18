import json
import urllib.request

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
    "AGUASCALIENTES": "Aguascalientes",
    "BAJA CALIFORNIA": "Baja California",
    "BAJA CALIFORNIA SUR": "Baja California Sur",
    "CAMPECHE": "Campeche",
    "CHIAPAS": "Chiapas",
    "CHIHUAHUA": "Chihuahua",
    "CIUDAD DE MEXICO": "Ciudad de México",
    "COAHUILA": "Coahuila",
    "COLIMA": "Colima",
    "DURANGO": "Durango",
    "ESTADO DE MEXICO": "México",
    "GUANAJUATO": "Guanajuato",
    "GUERRERO": "Guerrero",
    "HIDALGO": "Hidalgo",
    "JALISCO": "Jalisco",
    "MICHOACAN": "Michoacán",
    "MORELOS": "Morelos",
    "NAYARIT": "Nayarit",
    "NUEVO LEON": "Nuevo León",
    "OAXACA": "Oaxaca",
    "PUEBLA": "Puebla",
    "QUERETARO": "Querétaro",
    "QUINTANA ROO": "Quintana Roo",
    "SAN LUIS POTOSI": "San Luis Potosí",
    "SINALOA": "Sinaloa",
    "SONORA": "Sonora",
    "TABASCO": "Tabasco",
    "TAMAULIPAS": "Tamaulipas",
    "TLAXCALA": "Tlaxcala",
    "VERACRUZ": "Veracruz",
    "YUCATAN": "Yucatán",
    "ZACATECAS": "Zacatecas",
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

def get_custom_ticks(max_value, n_ticks=5):
    import math
    if pd.isna(max_value) or max_value <= 0:
        return [0], ["$0"]
    raw_step = max_value / n_ticks
    mag = math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    mag_pow = 10 ** mag
    mag_m = raw_step / mag_pow
    if mag_m > 5: step = 10 * mag_pow
    elif mag_m > 2: step = 5 * mag_pow
    elif mag_m > 1: step = 2 * mag_pow
    else: step = 1 * mag_pow
    
    tickvals = []
    cur = 0
    while cur <= max_value * 1.05:
        tickvals.append(cur)
        cur += step
        
    ticktext = []
    for v in tickvals:
        if v == 0:
            ticktext.append("$0")
        elif v >= 1_000_000_000:
            ticktext.append(f"${v/1_000_000_000:,.1f} MM".replace(".0 MM", " MM"))
        elif v >= 1_000_000:
            ticktext.append(f"${v/1_000_000:,.1f} M".replace(".0 M", " M"))
        elif v >= 1_000:
            ticktext.append(f"${v/1_000:,.1f} K".replace(".0 K", " K"))
        else:
            ticktext.append(f"${v:,.0f}")
    return tickvals, ticktext

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
        'SELECT MIN("Fecha Registro"), MAX("Fecha Registro") FROM garantias'
    ).fetchone()
    bancos = con.execute(
        'SELECT DISTINCT "Banco(Nafin/BCMXT)" FROM garantias ORDER BY 1'
    ).fetchdf().iloc[:, 0].tolist()
    estados = con.execute(
        'SELECT DISTINCT "Estado_v2" FROM garantias ORDER BY 1'
    ).fetchdf().iloc[:, 0].tolist()
    return pd.Timestamp(fecha_min).date(), pd.Timestamp(fecha_max).date(), bancos, estados

@st.cache_data(show_spinner=False, ttl=86400)
def get_geojson_estados():
    url = "https://raw.githubusercontent.com/angelnmara/geojson/master/mexicoHigh.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None

def build_where(fecha_ini, fecha_fin, bancos_sel: list, estados_sel: list):
    clausulas = ['"Fecha Registro" BETWEEN ? AND ?']
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
        sql_date = 'CAST("Fecha Registro" AS DATE)'
    elif gran == "Semana":
        sql_date = 'date_trunc(\'week\', "Fecha Registro")'
    elif gran == "Quincena":
        sql_date = """CASE
            WHEN DAY(CAST("Fecha Registro" AS DATE)) <= 15
            THEN CAST(STRFTIME(CAST("Fecha Registro" AS DATE), '%Y-%m-01') AS DATE)
            ELSE CAST(STRFTIME(CAST("Fecha Registro" AS DATE), '%Y-%m-16') AS DATE)
        END"""
    elif gran == "Mes":
        sql_date = 'date_trunc(\'month\', "Fecha Registro")'
    elif gran == "Trimestre":
        sql_date = 'date_trunc(\'quarter\', "Fecha Registro")'
    elif gran == "Semestre":
        sql_date = """CASE
            WHEN MONTH(CAST("Fecha Registro" AS DATE)) <= 6
            THEN CAST(STRFTIME(CAST("Fecha Registro" AS DATE), '%Y-01-01') AS DATE)
            ELSE CAST(STRFTIME(CAST("Fecha Registro" AS DATE), '%Y-07-01') AS DATE)
        END"""
    elif gran == "Año":
        sql_date = 'date_trunc(\'year\', "Fecha Registro")'
    else:
        sql_date = 'date_trunc(\'month\', "Fecha Registro")'
    sql = f"""
        SELECT
            {sql_date} AS periodo,
            SUM("Monto Inicial") AS colocacion,
            SUM("Ultimo Saldo") AS saldo
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
        otros_count = len(df_sorted) - TOP_N
        otros_val = df_sorted.iloc[TOP_N:]["saldo"].sum()
        df_plot.loc[len(df_plot)] = [f"Otros intermediarios ({otros_count})", otros_val]
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
        sort=False,
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
    t_vals, t_texts = get_custom_ticks(df_plot["saldo"].max())
    fig.update_xaxes(title=None, tickangle=-20, tickfont=dict(size=10))
    fig.update_yaxes(title=None, tickmode="array", tickvals=t_vals, ticktext=t_texts)
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

def marcar_rango_personalizado():
    st.session_state["preset_selector"] = None

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
        st.markdown("**Atajos de periodo**")
        st.selectbox(
            "Atajos de periodo",
            options=["Histórico", "YTD", "Últimos 6M", "Último Año"],
            key="preset_selector",
            label_visibility="collapsed",
            on_change=apply_preset,
        )
    with fc2:
        st.markdown("**Periodo (fecha)**")
        rango_fechas = st.date_input(
            "Periodo",
            min_value=fecha_min,
            max_value=fecha_max,
            key="filtro_rango_fechas",
            label_visibility="collapsed",
            on_change=marcar_rango_personalizado,
        )
    with fc3:
        st.markdown("**Banco**")
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
    st.session_state["_ultimo_rango_valido"] = (fecha_ini, fecha_fin)
else:
    # Selección en curso (solo se ha elegido la fecha inicial): se conserva
    # el último rango completo en vez de recalcular con un fin supuesto.
    fecha_ini, fecha_fin = st.session_state.get("_ultimo_rango_valido", (fecha_min, fecha_max))
    st.info("Selecciona la fecha final para actualizar el periodo.", icon=":material/event:")

filtros_bancos = tuple(bancos_sel)
filtros_estados = tuple(estados_sel)

st.caption(f"Mostrando datos del **{fecha_ini:%d/%m/%Y}** al **{fecha_fin:%d/%m/%Y}**.")

kpis = query_kpis(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

pct_amortizado = 0.0
if kpis["monto_inicial"] and kpis["monto_inicial"] > 0:
    pct_amortizado = (1 - kpis["saldo_vivo"] / kpis["monto_inicial"]) * 100

st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

m1, m2, m3, m4, m5 = st.columns(5)
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
        <div class="metric-label">Saldo</div>
        <div class="metric-val">{fmt_mdp(kpis["saldo_vivo"])}</div>
        <div class="metric-sub">Pendiente por amortizar</div>
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
with m5:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Intermediarios</div>
        <div class="metric-val">{fmt_num(kpis["intermediarios"])}</div>
        <div class="metric-sub">Entidades financieras participantes</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

with st.container(border=True):
    col_hdr1, col_hdr2 = st.columns([3.5, 1.2])
    with col_hdr1:
        st.markdown('<p class="chart-title">Evolución temporal de la colocación y saldo</p>', unsafe_allow_html=True)
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
        df_evol["periodo_dt"] = pd.to_datetime(df_evol["periodo"])
        df_evol = df_evol.sort_values("periodo_dt").reset_index(drop=True)
        
        df_evol["var_periodo_col"] = df_evol["colocacion"].pct_change()
        df_evol["var_periodo_sal"] = df_evol["saldo"].pct_change()
        
        offsets = {"Día": 365, "Semana": 52, "Quincena": 24, "Mes": 12, "Trimestre": 4, "Semestre": 2, "Año": 1}
        offset = offsets.get(gran_sel, 12)
        
        df_evol["var_anual_col"] = df_evol["colocacion"].pct_change(periods=offset)
        df_evol["var_anual_sal"] = df_evol["saldo"].pct_change(periods=offset)
        
        def fmt_pct(val):
            if pd.isna(val) or val == float('inf') or val == float('-inf'): return "N/D"
            return f"{val:+.1%}"
            
        df_evol["hover_label"] = df_evol["periodo"].apply(lambda x: fmt_periodo(x, gran_sel))
        df_evol["var_periodo_col_str"] = df_evol["var_periodo_col"].apply(fmt_pct)
        df_evol["var_anual_col_str"] = df_evol["var_anual_col"].apply(fmt_pct)
        df_evol["var_periodo_sal_str"] = df_evol["var_periodo_sal"].apply(fmt_pct)
        df_evol["var_anual_sal_str"] = df_evol["var_anual_sal"].apply(fmt_pct)
        
        if gran_sel == "Año":
            ht_col = "<b>%{customdata[0]}</b><br>Colocación: $%{y:,.0f}<br>Variación anual: %{customdata[1]}<extra></extra>"
            ht_sal = "<b>%{customdata[0]}</b><br>Saldo: $%{y:,.0f}<br>Variación anual: %{customdata[2]}<extra></extra>"
            custom_data = df_evol[["hover_label", "var_periodo_col_str", "var_periodo_sal_str"]].values
        else:
            ht_col = "<b>%{customdata[0]}</b><br>Colocación: $%{y:,.0f}<br>Var. periodo: %{customdata[1]}<br>Var. anual: %{customdata[2]}<extra></extra>"
            ht_sal = "<b>%{customdata[0]}</b><br>Saldo: $%{y:,.0f}<br>Var. periodo: %{customdata[3]}<br>Var. anual: %{customdata[4]}<extra></extra>"
            custom_data = df_evol[["hover_label", "var_periodo_col_str", "var_anual_col_str", "var_periodo_sal_str", "var_anual_sal_str"]].values

        pico = df_evol.loc[df_evol["colocacion"].idxmax()]
        pico_str = fmt_periodo(pico["periodo"], gran_sel)
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            fig_evol_col = go.Figure(go.Bar(
                x=df_evol["periodo"],
                y=df_evol["colocacion"],
                customdata=custom_data,
                marker=dict(color=PRIMARY),
                hovertemplate=ht_col,
            ))
            aplicar_tema(fig_evol_col, altura=330)
            t_vals_col, t_texts_col = get_custom_ticks(df_evol["colocacion"].max())
            fig_evol_col.update_yaxes(tickmode="array", tickvals=t_vals_col, ticktext=t_texts_col)
            fig_evol_col.update_layout(title="Colocación", title_font=dict(size=14, color=SLATE_700), margin=dict(t=40))
            st.plotly_chart(fig_evol_col, use_container_width=True, config={"displayModeBar": False})
            
        with col_chart2:
            fig_evol_sal = go.Figure(go.Bar(
                x=df_evol["periodo"],
                y=df_evol["saldo"],
                customdata=custom_data,
                marker=dict(color=SLATE_700),
                hovertemplate=ht_sal,
            ))
            aplicar_tema(fig_evol_sal, altura=330)
            t_vals_sal, t_texts_sal = get_custom_ticks(df_evol["saldo"].max())
            fig_evol_sal.update_yaxes(tickmode="array", tickvals=t_vals_sal, ticktext=t_texts_sal)
            fig_evol_sal.update_layout(title="Saldo", title_font=dict(size=14, color=SLATE_700), margin=dict(t=40))
            st.plotly_chart(fig_evol_sal, use_container_width=True, config={"displayModeBar": False})

with st.container(border=True):
        st.markdown('<p class="chart-title">Distribución del portafolio por programa</p>', unsafe_allow_html=True)
        df_prog = query_programas_distribucion(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)
        if df_prog.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            df_prog = df_prog.sort_values("monto", ascending=False)
            
            is_only_bancomext = len(filtros_bancos) == 1 and filtros_bancos[0] == "BANCOMEXT"
            
            if is_only_bancomext:
                top_prog = df_prog.iloc[0]
                part_prog = (top_prog["monto"] / df_prog["monto"].sum()) * 100

                fig_prog = px.bar(
                    df_prog,
                    x="programa",
                    y="monto",
                    color="monto",
                    color_continuous_scale=[SLATE_200, PRIMARY],
                    text=df_prog["monto"].apply(fmt_mdp),
                )
                fig_prog.update_traces(
                    textposition="outside",
                    hovertemplate="%{x}<br>Monto Garantizado: $%{y:,.0f}<extra></extra>",
                )
                fig_prog.update_coloraxes(showscale=False)
                aplicar_tema(fig_prog, altura=440)
                t_vals_prog, t_texts_prog = get_custom_ticks(df_prog["monto"].max())
                fig_prog.update_xaxes(title=None, tickangle=-35, tickfont=dict(size=10))
                fig_prog.update_yaxes(title=None, tickmode="array", tickvals=t_vals_prog, ticktext=t_texts_prog)
                st.plotly_chart(fig_prog, use_container_width=True, config={"displayModeBar": False})
            else:
                top_prog = df_prog.iloc[0]
                part_prog = (top_prog["monto"] / df_prog["monto"].sum()) * 100
                
                df_g1 = df_prog[df_prog['monto'] >= 1000000000]
                df_g2 = df_prog[(df_prog['monto'] >= 100000000) & (df_prog['monto'] < 1000000000)]
                df_g3 = df_prog[(df_prog['monto'] >= 10000000) & (df_prog['monto'] < 100000000)]
                df_g4 = df_prog[df_prog['monto'] < 10000000]
                
                c1, c2 = st.columns(2)
                c3, c4 = st.columns(2)
                
                def plot_grid_chart(df_sub, col_st, title_sub):
                    with col_st:
                        if df_sub.empty:
                            st.markdown(f'<p class="chart-insight" style="margin-top: 15px;"><b>{title_sub}</b><br>Sin programas en esta escala.</p>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<p class="chart-insight" style="margin-top: 15px;"><b>{title_sub}</b></p>', unsafe_allow_html=True)
                            fig_sub = px.bar(
                                df_sub, x="programa", y="monto", color="monto",
                                color_continuous_scale=[SLATE_200, PRIMARY],
                                text=df_sub["monto"].apply(fmt_mdp)
                            )
                            fig_sub.update_traces(
                                textposition="outside",
                                hovertemplate="%{x}<br>Monto Garantizado: $%{y:,.0f}<extra></extra>",
                            )
                            fig_sub.update_coloraxes(showscale=False)
                            aplicar_tema(fig_sub, altura=350)
                            t_vals_sub, t_texts_sub = get_custom_ticks(df_sub["monto"].max())
                            fig_sub.update_xaxes(title=None, tickangle=-35, tickfont=dict(size=9))
                            fig_sub.update_yaxes(title=None, tickmode="array", tickvals=t_vals_sub, ticktext=t_texts_sub)
                            st.plotly_chart(fig_sub, use_container_width=True, config={"displayModeBar": False})
                
                plot_grid_chart(df_g1, c1, "Escala: Mayor a 1,000 MDP (MMDP)")
                plot_grid_chart(df_g2, c2, "Escala: 100 MDP a 1,000 MDP")
                plot_grid_chart(df_g3, c3, "Escala: 10 MDP a 100 MDP")
                plot_grid_chart(df_g4, c4, "Escala: Menor a 10 MDP")

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
                fig_donut_bc = render_donut_chart(df_inter_bcmxt, "BANCOMEXT", PALETTE_BCMXT)
                if fig_donut_bc:
                    st.plotly_chart(fig_donut_bc, use_container_width=True, config={"displayModeBar": False})

df_mapa = query_mapa(fecha_ini, fecha_fin, filtros_bancos, filtros_estados)

if df_mapa.empty:
    with st.container(border=True):
        st.info("No hay datos territoriales para los filtros seleccionados.")
else:
    geojson_data = get_geojson_estados()
    if geojson_data is None:
        st.warning("No fue posible cargar la geometría de los estados en este momento. Intenta de nuevo más tarde.")
    else:
        df_mapa_plot = df_mapa.copy()
        df_mapa_plot["estado_geo"] = df_mapa_plot["estado"].replace(NAME_NORMALIZER)
        
        def create_map(color_col, z_format):
            fig = px.choropleth(
                df_mapa_plot,
                geojson=geojson_data,
                locations="estado_geo",
                featureidkey="properties.name",
                color=color_col,
                color_continuous_scale="Teal",
                hover_name="estado",
            )
            if color_col == "saldo":
                custom_data = df_mapa_plot[["monto_garantizado", "acreditados"]]
                ht = "<b>%{hovertext}</b><br><span style='color:#7dd3c8; font-weight:700;'>Saldo:</span> $%{z:,.0f}<br><span style='color:#7dd3c8; font-weight:700;'>Monto Garantizado:</span> $%{customdata[0]:,.0f}<br><span style='color:#7dd3c8; font-weight:700;'>Acreditados:</span> %{customdata[1]:,}<extra></extra>"
            else:
                custom_data = df_mapa_plot[["saldo", "acreditados"]]
                ht = "<b>%{hovertext}</b><br><span style='color:#7dd3c8; font-weight:700;'>Monto Garantizado:</span> $%{z:,.0f}<br><span style='color:#7dd3c8; font-weight:700;'>Saldo:</span> $%{customdata[0]:,.0f}<br><span style='color:#7dd3c8; font-weight:700;'>Acreditados:</span> %{customdata[1]:,}<extra></extra>"
            
            fig.update_traces(
                customdata=custom_data,
                hovertemplate=ht,
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
            fig.update_geos(fitbounds="locations", visible=False, bgcolor="#F8FAFC")
            t_vals_map, t_texts_map = get_custom_ticks(df_mapa_plot[color_col].max())
            
            fig.update_layout(
                margin={"r": 0, "t": 0, "l": 0, "b": 0, "pad": 0},
                height=550,
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
                    tickmode="array",
                    tickvals=t_vals_map,
                    ticktext=t_texts_map,
                ),
            )
            return fig

        fig_saldo = create_map("saldo", "$%{z:,.0f}")

        with st.container(border=True):
            st.markdown('<p class="chart-title">Distribución territorial: Saldo</p>', unsafe_allow_html=True)
            lider = df_mapa.sort_values("saldo", ascending=False).iloc[0]
            st.plotly_chart(fig_saldo, use_container_width=True, config={"displayModeBar": False})
            
            st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
            st.markdown('<p class="chart-title">Detalle por Entidad Federativa</p>', unsafe_allow_html=True)
            
            df_tabla = df_mapa.sort_values("saldo", ascending=False).reset_index(drop=True)
            df_tabla["saldo"] = df_tabla["saldo"] / 1_000_000
            df_tabla["monto_garantizado"] = df_tabla["monto_garantizado"] / 1_000_000

            df_tabla = df_tabla.rename(columns={
                "estado": "Estado",
                "saldo": "Saldo (MDP)",
                "monto_garantizado": "Monto Garantizado (MDP)",
                "acreditados": "Acreditados"
            })
            
            st.dataframe(
                df_tabla,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Estado": st.column_config.TextColumn("Entidad Federativa"),
                    "Saldo (MDP)": st.column_config.NumberColumn("Saldo (MDP)", format="$ %.1f"),
                    "Monto Garantizado (MDP)": st.column_config.NumberColumn("Monto Garantizado (MDP)", format="$ %.1f"),
                    "Acreditados": st.column_config.NumberColumn("Acreditados", format="%d"),
                }
            )

st.caption(
    f"Datos filtrados del {fecha_ini:%d/%m/%Y} al {fecha_fin:%d/%m/%Y} · "
    f"{fmt_num(kpis['intermediarios'])} intermediarios activos en la selección."
)
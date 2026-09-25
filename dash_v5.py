import json
import urllib.request

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="Portafolio de Garantías | NAFIN · BANCOMEXT",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PARQUET_PATH = "data/intermediate/garantias_v5_part/**/*.parquet"

BG = "#F8FAFC"
PRIMARY = "#2596BE"
PRIMARY_DARK = "#1C7691"
ACCENT_AMBER = "#F59E0B"
SLATE_100 = "#F1F5F9"
SLATE_200 = "#E2E8F0"
SLATE_500 = "#64748B"
SLATE_700 = "#334155"
SLATE_900 = "#0F172A"

PALETA_ESTRATO = ["#8AD1E6", "#5CB3D1", PRIMARY, PRIMARY_DARK, SLATE_700, "#CBD5E1"]
ORDEN_ESTRATO_PREFERIDO = ["MICRO", "PEQUENA", "MEDIANA", "GRANDE"]

MESES_ES = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}

# Normaliza los nombres canónicos (mayúsculas, salida de data_prep_v5) al
# formato corto que usa el GeoJSON de referencia.
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
}


def fmt_mdp(valor) -> str:
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


def fmt_pct(valor) -> str:
    if valor is None or pd.isna(valor):
        return "N/D"
    return f"{valor:,.2f}%"


def fmt_periodo(fecha) -> str:
    if pd.isna(fecha):
        return "N/D"
    ts = pd.Timestamp(fecha)
    return f"{MESES_ES.get(ts.month, '')} {ts.year}"


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


def _norm_estrato(v: str) -> str:
    v = str(v).upper().strip()
    for a, b in (("Á", "A"), ("É", "E"), ("Í", "I"), ("Ó", "O"), ("Ú", "U"), ("Ñ", "N")):
        v = v.replace(a, b)
    return v


def construir_mapa_color_estrato(valores_estrato) -> dict:
    """Asigna colores a los estratos, respetando el orden Micro -> Grande
    cuando los valores coinciden con esa nomenclatura, y cayendo a la
    paleta secuencial para cualquier otro valor no anticipado."""
    valores_unicos = list(dict.fromkeys(valores_estrato))

    def orden_key(v):
        vn = _norm_estrato(v)
        return ORDEN_ESTRATO_PREFERIDO.index(vn) if vn in ORDEN_ESTRATO_PREFERIDO else len(ORDEN_ESTRATO_PREFERIDO)

    valores_ordenados = sorted(valores_unicos, key=orden_key)
    return {v: PALETA_ESTRATO[i % len(PALETA_ESTRATO)] for i, v in enumerate(valores_ordenados)}


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
        SELECT * FROM read_parquet('{PARQUET_PATH}', hive_partitioning=true)
    """)
    return con


@st.cache_data(show_spinner=False)
def get_bounds():
    con = get_connection()
    periodos = con.execute(
        "SELECT DISTINCT periodo FROM garantias WHERE periodo IS NOT NULL ORDER BY periodo"
    ).fetchdf()["periodo"].tolist()
    bancos = con.execute(
        "SELECT DISTINCT banco FROM garantias WHERE banco IS NOT NULL ORDER BY 1"
    ).fetchdf().iloc[:, 0].tolist()
    estados = con.execute(
        "SELECT DISTINCT estado FROM garantias WHERE estado IS NOT NULL ORDER BY 1"
    ).fetchdf().iloc[:, 0].tolist()
    estratos = con.execute(
        "SELECT DISTINCT estrato FROM garantias WHERE estrato IS NOT NULL ORDER BY 1"
    ).fetchdf().iloc[:, 0].tolist()
    return [pd.Timestamp(p) for p in periodos], bancos, estados, estratos


@st.cache_data(show_spinner=False, ttl=86400)
def get_geojson_estados():
    url = "https://raw.githubusercontent.com/angelnmara/geojson/master/mexicoHigh.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def build_where_snapshot(periodo_corte, bancos_sel: list, estados_sel: list, estratos_sel: list):
    clausulas = ["periodo = ?"]
    params = [periodo_corte]
    if bancos_sel:
        marcadores = ",".join(["?"] * len(bancos_sel))
        clausulas.append(f"banco IN ({marcadores})")
        params.extend(bancos_sel)
    if estados_sel:
        marcadores = ",".join(["?"] * len(estados_sel))
        clausulas.append(f"estado IN ({marcadores})")
        params.extend(estados_sel)
    if estratos_sel:
        marcadores = ",".join(["?"] * len(estratos_sel))
        clausulas.append(f"estrato IN ({marcadores})")
        params.extend(estratos_sel)
    return " AND ".join(clausulas), params

def build_where_rango(periodo_ini, periodo_fin, bancos_sel: list, estados_sel: list, estratos_sel: list):
    clausulas = ["periodo BETWEEN ? AND ?"]
    params = [periodo_ini, periodo_fin]
    if bancos_sel:
        marcadores = ",".join(["?"] * len(bancos_sel))
        clausulas.append(f"banco IN ({marcadores})")
        params.extend(bancos_sel)
    if estados_sel:
        marcadores = ",".join(["?"] * len(estados_sel))
        clausulas.append(f"estado IN ({marcadores})")
        params.extend(estados_sel)
    if estratos_sel:
        marcadores = ",".join(["?"] * len(estratos_sel))
        clausulas.append(f"estrato IN ({marcadores})")
        params.extend(estratos_sel)
    return " AND ".join(clausulas), params

@st.cache_data(show_spinner=False)
def query_kpis(periodo_corte, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple) -> pd.Series:
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, list(bancos_sel), list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT
            SUM(monto_colocado)                        AS monto_colocado,
            SUM(saldo)                                  AS saldo,
            SUM(tasa * saldo) / NULLIF(SUM(saldo), 0)   AS tasa_prom,
            COUNT(DISTINCT rfc)                         AS acreditados,
            COUNT(DISTINCT intermediario)               AS intermediarios
        FROM garantias
        WHERE {where_sql}
    """
    return con.execute(sql, params).fetchdf().iloc[0]

@st.cache_data(show_spinner=False)
def query_evolucion(periodo_ini, periodo_fin, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where_rango(periodo_ini, periodo_fin, list(bancos_sel), list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT
            periodo,
            SUM(monto_colocado)                        AS monto_colocado,
            SUM(saldo)                                  AS saldo,
            SUM(tasa * saldo) / NULLIF(SUM(saldo), 0)   AS tasa_prom
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY 1
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_estrato(periodo_corte, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, list(bancos_sel), list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT estrato, SUM(saldo) AS saldo
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM(saldo) > 0
        ORDER BY saldo DESC
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_top_programas(periodo_corte, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, list(bancos_sel), list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT
            programa,
            SUM(saldo)                                 AS saldo,
            SUM(tasa * saldo) / NULLIF(SUM(saldo), 0)  AS tasa_prom
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM(saldo) > 0
        ORDER BY saldo DESC
        LIMIT 10
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_programas_distribucion(periodo_corte, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, list(bancos_sel), list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT
            programa,
            SUM(saldo) AS monto
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM(saldo) > 0
        ORDER BY monto DESC
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_top_intermediarios(periodo_corte, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, list(bancos_sel), list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT intermediario, SUM(saldo) AS saldo
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM(saldo) > 0
        ORDER BY saldo DESC
        LIMIT 10
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_intermediarios_por_estrato(
    periodo_corte, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple, intermediarios: tuple
) -> pd.DataFrame:
    if not intermediarios:
        return pd.DataFrame(columns=["intermediario", "estrato", "saldo"])
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, list(bancos_sel), list(estados_sel), list(estratos_sel))
    marcadores = ",".join(["?"] * len(intermediarios))
    sql = f"""
        SELECT intermediario, estrato, SUM(saldo) AS saldo
        FROM garantias
        WHERE {where_sql} AND intermediario IN ({marcadores})
        GROUP BY 1, 2
    """
    params = params + list(intermediarios)
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_intermediarios_banco(periodo_corte, banco: str, estados_sel: tuple, estratos_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, [banco], list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT
            intermediario,
            SUM(saldo) AS saldo
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM(saldo) > 0
        ORDER BY saldo DESC
    """
    return con.execute(sql, params).fetchdf()

@st.cache_data(show_spinner=False)
def query_mapa(periodo_corte, bancos_sel: tuple, estados_sel: tuple, estratos_sel: tuple) -> pd.DataFrame:
    con = get_connection()
    where_sql, params = build_where_snapshot(periodo_corte, list(bancos_sel), list(estados_sel), list(estratos_sel))
    sql = f"""
        SELECT
            estado,
            SUM(saldo)                                 AS saldo,
            COUNT(DISTINCT rfc)                        AS acreditados,
            SUM(tasa * saldo) / NULLIF(SUM(saldo), 0)  AS tasa_prom
        FROM garantias
        WHERE {where_sql}
        GROUP BY 1
        HAVING SUM(saldo) > 0
        ORDER BY saldo DESC
    """
    return con.execute(sql, params).fetchdf()


PALETTE_NAFIN = ["#2596BE", "#5CB3D1", "#8AD1E6", "#1C7691", "#0F4C5C", "#CBD5E1", "#94A3B8"]
PALETTE_BCMXT = ["#334155", "#475569", "#64748B", "#94A3B8", "#CBD5E1", "#1E293B", "#0F172A"]

def render_donut_chart(df_data: pd.DataFrame, banco_nombre: str, palette: list):
    if df_data.empty: return None
    TOP_N = 6
    df_sorted = df_data.sort_values("saldo", ascending=False).reset_index(drop=True)
    if len(df_sorted) > TOP_N:
        df_plot = df_sorted.iloc[:TOP_N].copy()
        otros_count = len(df_sorted) - TOP_N
        otros_val = df_sorted.iloc[TOP_N:]["saldo"].sum()
        df_plot.loc[len(df_plot)] = [f"Otros intermediarios ({otros_count})", otros_val]
    else:
        df_plot = df_sorted
    fig = px.pie(df_plot, names="intermediario", values="saldo", hole=0.6, color_discrete_sequence=palette)
    fig.update_traces(textposition="outside", textinfo="percent", hovertemplate="%{label}<br>Saldo: $%{value:,.0f} (%{percent})<extra></extra>", sort=False)
    aplicar_tema(fig, altura=380)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.20, xanchor="center", x=0.5, font=dict(size=10)), margin=dict(l=8, r=8, t=8, b=100))
    return fig

def render_column_chart(df_data: pd.DataFrame, banco_nombre: str):
    if df_data.empty: return None
    scale_colors = [SLATE_200, PRIMARY] if banco_nombre == "NAFIN" else [SLATE_200, SLATE_700]
    df_plot = df_data.head(8)
    fig = px.bar(df_plot, x="intermediario", y="saldo", color="saldo", color_continuous_scale=scale_colors, text=df_plot["saldo"].apply(fmt_mdp))
    fig.update_traces(textposition="outside", hovertemplate="<b>%{x}</b><br>Saldo: $%{y:,.0f}<extra></extra>")
    fig.update_coloraxes(showscale=False)
    aplicar_tema(fig, altura=380)
    t_vals, t_texts = get_custom_ticks(df_plot["saldo"].max())
    fig.update_xaxes(title=None, tickangle=-20, tickfont=dict(size=10))
    fig.update_yaxes(title=None, tickmode="array", tickvals=t_vals, ticktext=t_texts)
    fig.update_layout(margin=dict(l=8, r=8, t=15, b=30))
    return fig

# ---------------------------------------------------------------------------
# Filtros (barra superior)
# ---------------------------------------------------------------------------
periodos_disponibles, bancos_disponibles, estados_disponibles, estratos_disponibles = get_bounds()
periodo_min, periodo_max = periodos_disponibles[0], periodos_disponibles[-1]
MAPA_COLOR_ESTRATO = construir_mapa_color_estrato(estratos_disponibles)

if "filtro_rango_periodo" not in st.session_state:
    st.session_state["filtro_rango_periodo"] = (periodo_min, periodo_max)
if "filtro_bancos" not in st.session_state:
    st.session_state["filtro_bancos"] = []
if "filtro_estados" not in st.session_state:
    st.session_state["filtro_estados"] = []
if "filtro_estratos" not in st.session_state:
    st.session_state["filtro_estratos"] = []
if "preset_selector" not in st.session_state:
    st.session_state["preset_selector"] = "Histórico"

def apply_preset():
    preset = st.session_state["preset_selector"]
    if preset == "YTD":
        f_calc = pd.Timestamp(periodo_max.year, 1, 1)
        valid = [p for p in periodos_disponibles if p >= f_calc]
        st.session_state["filtro_rango_periodo"] = (valid[0] if valid else periodo_min, periodo_max)
    elif preset == "Últimos 6M":
        f_calc = pd.Timestamp((periodo_max - pd.DateOffset(months=5)).year, (periodo_max - pd.DateOffset(months=5)).month, 1)
        valid = [p for p in periodos_disponibles if p >= f_calc]
        st.session_state["filtro_rango_periodo"] = (valid[0] if valid else periodo_min, periodo_max)
    elif preset == "Último Año":
        f_calc = pd.Timestamp((periodo_max - pd.DateOffset(years=1) + pd.DateOffset(months=1)).year, (periodo_max - pd.DateOffset(years=1) + pd.DateOffset(months=1)).month, 1)
        valid = [p for p in periodos_disponibles if p >= f_calc]
        st.session_state["filtro_rango_periodo"] = (valid[0] if valid else periodo_min, periodo_max)
    elif preset == "Histórico":
        st.session_state["filtro_rango_periodo"] = (periodo_min, periodo_max)

def marcar_rango_personalizado():
    st.session_state["preset_selector"] = None

def reset_all_filters():
    st.session_state["filtro_rango_periodo"] = (periodo_min, periodo_max)
    st.session_state["filtro_bancos"] = []
    st.session_state["filtro_estados"] = []
    st.session_state["filtro_estratos"] = []
    st.session_state["preset_selector"] = "Histórico"

st.markdown("<h1>Portafolio de Garantías</h1>", unsafe_allow_html=True)
st.markdown(
    '<p class="subtitulo">Consolidado NAFIN · BANCOMEXT — programas de fomento y financiamiento de segundo piso</p>',
    unsafe_allow_html=True,
)

with st.container(border=True):
    fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([1.0, 1.4, 1.0, 1.0, 1.0, 0.4])
    with fc1:
        st.markdown("**Atajos**")
        st.selectbox(
            "Atajos",
            options=["Histórico", "YTD", "Últimos 6M", "Último Año"],
            key="preset_selector",
            label_visibility="collapsed",
            on_change=apply_preset,
        )
    with fc2:
        st.markdown("**Periodo (mensual)**")
        # Prevenir TypeError asignando un value seguro desde el session state y manejando su tamaño al vuelo
        val_slider = st.select_slider(
            "Periodo",
            options=periodos_disponibles,
            value=st.session_state["filtro_rango_periodo"],
            format_func=fmt_periodo,
            label_visibility="collapsed",
            on_change=marcar_rango_personalizado,
        )
        if isinstance(val_slider, (tuple, list)) and len(val_slider) == 2:
            periodo_ini, periodo_fin = val_slider
        else:
            periodo_ini = periodo_fin = val_slider
        st.session_state["filtro_rango_periodo"] = (periodo_ini, periodo_fin)
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
        st.markdown("**Estrato**")
        estratos_sel = st.multiselect(
            "Estrato",
            options=estratos_disponibles,
            placeholder="Todos los estratos",
            key="filtro_estratos",
            label_visibility="collapsed",
        )
    with fc6:
        st.markdown("**&nbsp;**")
        st.button("🔄", on_click=reset_all_filters, use_container_width=True, help="Restablecer Filtros")

filtros_bancos = tuple(bancos_sel)
filtros_estados = tuple(estados_sel)
filtros_estratos = tuple(estratos_sel)

# ---------------------------------------------------------------------------
# KPIs (5 tarjetas)
# ---------------------------------------------------------------------------
# Todo lo estático ahora consulta únicamente con periodo_fin (fotografía de cierre)
kpis = query_kpis(periodo_fin, filtros_bancos, filtros_estados, filtros_estratos)

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Colocado por Intermediarios</div>
        <div class="metric-val">{fmt_mdp(kpis["monto_colocado"])}</div>
        <div class="metric-sub">Total de crédito colocado</div>
    </div>
    """, unsafe_allow_html=True)
with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Saldo Contingente</div>
        <div class="metric-val">{fmt_mdp(kpis["saldo"])}</div>
        <div class="metric-sub">Consolidado contingente vigente</div>
    </div>
    """, unsafe_allow_html=True)
with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Tasa Interés Promedio</div>
        <div class="metric-val">{fmt_pct(kpis["tasa_prom"])}</div>
        <div class="metric-sub">Ponderada por saldo</div>
    </div>
    """, unsafe_allow_html=True)
with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Acreditados Únicos</div>
        <div class="metric-val">{fmt_num(kpis["acreditados"])}</div>
        <div class="metric-sub">RFC distintos en la selección</div>
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

st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Evolución temporal: Aquí SÍ usamos el rango completo (periodo_ini a periodo_fin)
# ---------------------------------------------------------------------------
with st.container(border=True):
    df_evol = query_evolucion(periodo_ini, periodo_fin, filtros_bancos, filtros_estados, filtros_estratos)
    if df_evol.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        df_evol = df_evol.sort_values("periodo").reset_index(drop=True)
        df_evol["periodo_label"] = df_evol["periodo"].apply(fmt_periodo)

        c_evol1, c_evol2, c_evol3 = st.columns(3)

        with c_evol1:
            st.markdown('<p class="chart-insight"><b>Monto Colocado</b></p>', unsafe_allow_html=True)
            fig_coloc = px.line(df_evol, x="periodo", y="monto_colocado", custom_data=["periodo_label"], markers=True)
            fig_coloc.update_traces(line_color=PRIMARY, line_width=3, marker=dict(size=6), hovertemplate="<b>%{customdata[0]}</b><br>Monto Colocado: $%{y:,.0f}<extra></extra>")
            aplicar_tema(fig_coloc, altura=280)
            t_vals1, t_texts1 = get_custom_ticks(df_evol["monto_colocado"].max())
            fig_coloc.update_yaxes(tickmode="array", tickvals=t_vals1, ticktext=t_texts1, title=None)
            fig_coloc.update_xaxes(title=None)
            fig_coloc.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_coloc, use_container_width=True, config={"displayModeBar": False})

        with c_evol2:
            st.markdown('<p class="chart-insight"><b>Saldo</b></p>', unsafe_allow_html=True)
            fig_saldo = px.line(df_evol, x="periodo", y="saldo", custom_data=["periodo_label"], markers=True)
            fig_saldo.update_traces(line_color=SLATE_700, line_width=3, marker=dict(size=6), hovertemplate="<b>%{customdata[0]}</b><br>Saldo: $%{y:,.0f}<extra></extra>")
            aplicar_tema(fig_saldo, altura=280)
            t_vals2, t_texts2 = get_custom_ticks(df_evol["saldo"].max())
            fig_saldo.update_yaxes(tickmode="array", tickvals=t_vals2, ticktext=t_texts2, title=None)
            fig_saldo.update_xaxes(title=None)
            fig_saldo.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_saldo, use_container_width=True, config={"displayModeBar": False})

        with c_evol3:
            st.markdown('<p class="chart-insight"><b>Tasa de Interés Promedio</b></p>', unsafe_allow_html=True)
            fig_tasa = px.line(df_evol, x="periodo", y="tasa_prom", custom_data=["periodo_label"], markers=True)
            fig_tasa.update_traces(line_color=ACCENT_AMBER, line_width=3, marker=dict(size=6), hovertemplate="<b>%{customdata[0]}</b><br>Tasa Prom.: %{y:.2f}%<extra></extra>")
            aplicar_tema(fig_tasa, altura=280)
            fig_tasa.update_yaxes(title=None, ticksuffix="%")
            fig_tasa.update_xaxes(title=None)
            fig_tasa.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_tasa, use_container_width=True, config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# Distribución por Programa (Cuadrícula v4 - Ajustada a la escala del saldo)
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown('<p class="chart-title">Distribución del portafolio por programa</p>', unsafe_allow_html=True)
    df_prog_dist = query_programas_distribucion(periodo_fin, filtros_bancos, filtros_estados, filtros_estratos)
    if df_prog_dist.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        df_prog_dist = df_prog_dist.sort_values("monto", ascending=False)
        is_only_bancomext = len(filtros_bancos) == 1 and filtros_bancos[0] == "BANCOMEXT"
        
        if is_only_bancomext:
            fig_prog = px.bar(
                df_prog_dist, x="programa", y="monto", color="monto",
                color_continuous_scale=[SLATE_200, PRIMARY],
                text=df_prog_dist["monto"].apply(fmt_mdp),
            )
            fig_prog.update_traces(textposition="outside", hovertemplate="%{x}<br>Saldo: $%{y:,.0f}<extra></extra>")
            fig_prog.update_coloraxes(showscale=False)
            aplicar_tema(fig_prog, altura=440)
            t_vals_prog, t_texts_prog = get_custom_ticks(df_prog_dist["monto"].max())
            fig_prog.update_xaxes(title=None, tickangle=-35, tickfont=dict(size=10))
            fig_prog.update_yaxes(title=None, tickmode="array", tickvals=t_vals_prog, ticktext=t_texts_prog)
            st.plotly_chart(fig_prog, use_container_width=True, config={"displayModeBar": False})
        else:
            df_g1 = df_prog_dist[df_prog_dist['monto'] >= 1000000000]
            df_g2 = df_prog_dist[(df_prog_dist['monto'] >= 100000000) & (df_prog_dist['monto'] < 1000000000)]
            df_g3 = df_prog_dist[(df_prog_dist['monto'] >= 10000000) & (df_prog_dist['monto'] < 100000000)]
            df_g4 = df_prog_dist[df_prog_dist['monto'] < 10000000]
            
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
                        fig_sub.update_traces(textposition="outside", hovertemplate="%{x}<br>Saldo: $%{y:,.0f}<extra></extra>")
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

# ---------------------------------------------------------------------------
# Distribución por Estrato (donut) + Top 10 Intermediarios apilados
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([1, 1.4])

with col_left:
    with st.container(border=True):
        st.markdown('<p class="chart-title">Distribución del Saldo por Estrato</p>', unsafe_allow_html=True)
        df_estrato = query_estrato(periodo_fin, filtros_bancos, filtros_estados, filtros_estratos)
        if df_estrato.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            fig_donut = px.pie(
                df_estrato, names="estrato", values="saldo", hole=0.6,
                color="estrato", color_discrete_map=MAPA_COLOR_ESTRATO,
            )
            fig_donut.update_traces(
                textposition="outside", textinfo="percent",
                hovertemplate="%{label}<br>Saldo: $%{value:,.0f} (%{percent})<extra></extra>",
                sort=False,
            )
            aplicar_tema(fig_donut, altura=380)
            fig_donut.update_layout(
                legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5, font=dict(size=10)),
                margin=dict(l=8, r=8, t=8, b=70),
            )
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})

with col_right:
    with st.container(border=True):
        st.markdown('<p class="chart-title">Top 10 Intermediarios por Saldo, desglosado por Estrato</p>', unsafe_allow_html=True)
        df_top_int = query_top_intermediarios(periodo_fin, filtros_bancos, filtros_estados, filtros_estratos)
        if df_top_int.empty:
            st.info("No hay intermediarios con saldo activo para los filtros seleccionados.")
        else:
            orden_intermediarios = df_top_int["intermediario"].tolist()
            df_int_estrato = query_intermediarios_por_estrato(
                periodo_fin, filtros_bancos, filtros_estados, filtros_estratos, tuple(orden_intermediarios)
            )
            orden_invertido = list(reversed(orden_intermediarios))
            df_int_estrato["intermediario"] = pd.Categorical(
                df_int_estrato["intermediario"], categories=orden_invertido, ordered=True
            )
            df_int_estrato = df_int_estrato.sort_values(["intermediario", "estrato"])

            fig_int = px.bar(
                df_int_estrato, x="saldo", y="intermediario", color="estrato", orientation="h",
                color_discrete_map=MAPA_COLOR_ESTRATO,
                category_orders={"intermediario": orden_invertido},
            )
            fig_int.update_traces(hovertemplate="<b>%{y}</b><br>%{fullData.name}: $%{x:,.0f}<extra></extra>")
            fig_int.update_layout(barmode="stack")
            # Ajustamos a altura 380 para que embone perfectamente con la dona
            aplicar_tema(fig_int, altura=380)
            t_vals_i, t_texts_i = get_custom_ticks(df_top_int["saldo"].max())
            fig_int.update_xaxes(title=None, tickmode="array", tickvals=t_vals_i, ticktext=t_texts_i)
            fig_int.update_yaxes(title=None, tickfont=dict(size=10))
            st.plotly_chart(fig_int, use_container_width=True, config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# Intermediarios Financieros (Donas y Columnas v4) NAFIN / BCMXT
# ---------------------------------------------------------------------------
col_bank1, col_bank2 = st.columns(2)

if len(filtros_bancos) == 1:
    banco_solo = filtros_bancos[0]
    paleta_activa = PALETTE_NAFIN if banco_solo == "NAFIN" else PALETTE_BCMXT
    with col_bank1:
        with st.container(border=True):
            st.markdown(f'<p class="chart-title">Intermediarios Financieros — {banco_solo}</p>', unsafe_allow_html=True)
            df_inter_solo = query_intermediarios_banco(periodo_fin, banco_solo, filtros_estados, filtros_estratos)
            if df_inter_solo.empty:
                st.info(f"No hay intermediarios con saldo activo para {banco_solo}.")
            else:
                st.markdown('<p class="chart-insight">&nbsp;</p>', unsafe_allow_html=True)
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
            df_inter_nafin = query_intermediarios_banco(periodo_fin, "NAFIN", filtros_estados, filtros_estratos)
            if df_inter_nafin.empty:
                st.info("No hay intermediarios activos para NAFIN.")
            else:
                fig_donut_naf = render_donut_chart(df_inter_nafin, "NAFIN", PALETTE_NAFIN)
                if fig_donut_naf:
                    st.plotly_chart(fig_donut_naf, use_container_width=True, config={"displayModeBar": False})
    with col_bank2:
        with st.container(border=True):
            st.markdown('<p class="chart-title">Intermediarios Financieros — BANCOMEXT</p>', unsafe_allow_html=True)
            df_inter_bcmxt = query_intermediarios_banco(periodo_fin, "BANCOMEXT", filtros_estados, filtros_estratos)
            if df_inter_bcmxt.empty:
                st.info("No hay intermediarios activos para BANCOMEXT.")
            else:
                fig_donut_bc = render_donut_chart(df_inter_bcmxt, "BANCOMEXT", PALETTE_BCMXT)
                if fig_donut_bc:
                    st.plotly_chart(fig_donut_bc, use_container_width=True, config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# Mapa coroplético (Saldo) + tabla de desglose geográfico
# ---------------------------------------------------------------------------
df_mapa = query_mapa(periodo_fin, filtros_bancos, filtros_estados, filtros_estratos)

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

        fig_mapa = px.choropleth(
            df_mapa_plot, geojson=geojson_data, locations="estado_geo",
            featureidkey="properties.name", color="saldo",
            color_continuous_scale="Teal", hover_name="estado",
            custom_data=["acreditados", "tasa_prom"],
        )
        ht = (
            "<b>%{hovertext}</b><br>"
            "<span style='color:#7dd3c8; font-weight:700;'>Saldo:</span> $%{z:,.0f}<br>"
            "<span style='color:#7dd3c8; font-weight:700;'>Acreditados:</span> %{customdata[0]:,}<br>"
            "<span style='color:#7dd3c8; font-weight:700;'>Tasa Prom.:</span> %{customdata[1]:.2f}%<extra></extra>"
        )
        fig_mapa.update_traces(
            hovertemplate=ht,
            marker_line_color="white", marker_line_width=1.5,
            hoverlabel=dict(bgcolor="#0F172A", font_size=13, font_family="Inter, sans-serif", font_color="#F8FAFC", bordercolor="#0F172A", align="left"),
        )
        fig_mapa.update_geos(fitbounds="locations", visible=False, bgcolor=BG)
        t_vals_m, t_texts_m = get_custom_ticks(df_mapa_plot["saldo"].max())
        fig_mapa.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0, "pad": 0},
            height=550, autosize=True, dragmode=False,
            plot_bgcolor=BG, paper_bgcolor=BG,
            coloraxis_colorbar=dict(
                title="", thickness=10, len=0.88, y=0.5, yanchor="middle", outlinewidth=0,
                tickfont=dict(color=SLATE_500), tickmode="array", tickvals=t_vals_m, ticktext=t_texts_m,
            ),
        )

        with st.container(border=True):
            st.markdown('<p class="chart-title">Distribución territorial: Saldo</p>', unsafe_allow_html=True)
            st.plotly_chart(fig_mapa, use_container_width=True, config={"displayModeBar": False})

            st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
            st.markdown('<p class="chart-title">Detalle por Entidad Federativa</p>', unsafe_allow_html=True)

            df_tabla = df_mapa.sort_values("saldo", ascending=False).reset_index(drop=True)
            df_tabla["saldo"] = df_tabla["saldo"] / 1_000_000
            df_tabla = df_tabla.rename(columns={
                "estado": "Estado",
                "saldo": "Saldo (MDP)",
                "acreditados": "Acreditados",
                "tasa_prom": "Tasa Prom. (%)",
            })

            st.dataframe(
                df_tabla,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Estado": st.column_config.TextColumn("Entidad Federativa"),
                    "Saldo (MDP)": st.column_config.NumberColumn("Saldo (MDP)", format="$ %.1f"),
                    "Acreditados": st.column_config.NumberColumn("Acreditados", format="%d"),
                    "Tasa Prom. (%)": st.column_config.NumberColumn("Tasa Prom. (%)", format="%.2f%%"),
                },
            )

st.caption(
    f"Datos fotográficos al **{fmt_periodo(periodo_fin)}** (evolución desde **{fmt_periodo(periodo_ini)}**) · "
    f"{fmt_num(kpis['intermediarios'])} intermediarios activos en la selección."
)
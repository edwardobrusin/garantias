"""
data_prep_v5.py

Consolida los 3 parquet crudos del nuevo origen de datos, descarta columnas
innecesarias, renombra a nombres amigables, transforma el periodo YYYYMM a
datetime y aplica la lógica de limpieza heredada de v4 (programa, estado e
intermediario) para dejar un único parquet listo para el dashboard v5.
"""

import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
ARCHIVOS_RAW = [
    "data/raw/garantias24_0926.parquet",
    "data/raw/garantias25_0926.parquet",
    "data/raw/garantias26_0926.parquet",
]
DIR_SALIDA = "data/intermediate/garantias_v5_part"

# Columnas que se descartan por completo del análisis
COLUMNAS_DESCARTAR = [
    "Monto Garantizado (Saldo) (SUMA)",
    "Moneda Id (Saldo)",
]

# Renombrado de columnas complejas -> nombres amigables
MAPEO_COLUMNAS = {
    "CONSOLID CONTING (AGR)": "saldo",
    "Monto Credito Mn (SUMA)": "monto_colocado",
    "INT_RAZON_SOCIAL": "intermediario_raw",
    "Valor Tasa Interes": "tasa",
    "ESTRATO_DESCRIPCION": "estrato",
    "Fecha Consulta (Saldos) (MA)": "periodo_raw",
    "RFC_EMPRESA": "rfc",
    "PROGRAMA_DESCRIPCION": "programa_raw",
    "BANCO": "banco",
    "ESTADO": "estado_raw",
}


# ---------------------------------------------------------------------------
# 1. Lectura y consolidación de los 3 parquet
# ---------------------------------------------------------------------------
def cargar_datos() -> pd.DataFrame:
    dataframes = [pd.read_parquet(ruta) for ruta in ARCHIVOS_RAW]
    df = pd.concat(dataframes, ignore_index=True)
    df.columns = df.columns.str.strip()
    return df


# ---------------------------------------------------------------------------
# 2. Descarte de columnas innecesarias y renombrado
# ---------------------------------------------------------------------------
def descartar_y_renombrar(df: pd.DataFrame) -> pd.DataFrame:
    columnas_presentes = [c for c in COLUMNAS_DESCARTAR if c in df.columns]
    df = df.drop(columns=columnas_presentes)
    df = df.rename(columns=MAPEO_COLUMNAS)
    return df


# ---------------------------------------------------------------------------
# 3. Transformación de periodo YYYYMM (entero) -> primer día del mes (datetime)
# ---------------------------------------------------------------------------
def transformar_periodo(df: pd.DataFrame) -> pd.DataFrame:
    df["periodo"] = pd.to_datetime(
        df["periodo_raw"].astype("Int64").astype(str),
        format="%Y%m",
        errors="coerce",
    )
    df = df.drop(columns=["periodo_raw"])
    return df


# ---------------------------------------------------------------------------
# 4a. Limpieza de PROGRAMA_DESCRIPCION (heredada/adaptada de v4)
# ---------------------------------------------------------------------------
def limpiar_programa(texto) -> str:
    texto = str(texto).upper()

    if re.search(r'IMPULSO NAFIN|IMPUSO NAFIN|IMPULSO MIPYMES', texto): return 'IMPULSO NAFIN'
    if 'PRODUCTO NAFIN EMPRESARIAL' in texto: return 'PRODUCTO NAFIN EMPRESARIAL'

    if re.search(r'COMEX T-MEC|COMEX TMEC|COMERCIO EXTERIOR T-MEC|COMERCIO EXTERIOR EMPRESARIAL|PROGRAMA T-MEC|T-MEC PYME|TMEC|T-MEC', texto): return 'COMEX T-MEC'
    if re.search(r'MUJERES|MUJER PYME', texto): return 'MUJERES EMPRESARIAS'
    if 'AUTOMOTRIZ' in texto: return 'PROVEEDORES SECTOR AUTOMOTRIZ'
    if 'ELECTRICO' in texto and 'ELECTRONICO' in texto: return 'PROVEEDORES SECTOR ELECTRICO-ELECTRONICO'
    if 'TURISMO' in texto: return 'TURISMO'
    if 'PLAN MEXICO' in texto: return 'PLAN MEXICO'
    if 'MICRONEGOCIOS' in texto: return 'FINANCIAMIENTO A MICRONEGOCIOS'
    if re.search(r'TU PRIMER CR[EÉ]DITO', texto): return 'TU PRIMER CREDITO'
    if 'ECO CREDITO' in texto: return 'ECO CREDITO EMPRESARIAL'
    if 'COBERTURAS DIFERENCIADAS' in texto: return 'COBERTURAS DIFERENCIADAS'
    if 'CREDISUMINISTROS' in texto: return 'CREDISUMINISTROS'
    if re.search(r'FIANZAS PARI PASSU|GTIA SOBRE FIANZAS', texto): return 'GARANTIA SOBRE FIANZAS'
    if 'SUSTIT' in texto and 'VEHICULAR' in texto: return 'SUSTITUCION PARQUE VEHICULAR'
    if 'MIPYME MUNICIPAL' in texto: return 'MIPYME MUNICIPAL'
    if 'EFICIENCIA ENERGETICA' in texto or 'AHORRO ENERGETICO' in texto: return 'EFICIENCIA ENERGETICA'
    if 'SECTOR MEDICO' in texto: return 'SECTOR MEDICO'
    if 'RESTAURANTES' in texto: return 'RESTAURANTES'
    if re.search(r'REACT ECON|REAC ECON|REACTIVACION ECONOMICA', texto): return 'REACTIVACION ECONOMICA'
    if 'PROM DES ECON' in texto: return 'PROMOCION DESARROLLO ECONOMICO'
    if 'PYME HASTA 20 MDP' in texto: return 'PYME HASTA 20 MDP'
    if 'MIPYME (CREDITO COMERCIAL)' in texto: return 'MIPYME CREDITO COMERCIAL'
    if 'INUNDACIONES' in texto or 'HURACAN OTIS' in texto: return 'APOYO DESASTRES NATURALES'
    if 'GOBIERNO FEDERAL' in texto: return 'PROVEEDOR DEL GOBIERNO FEDERAL'
    if 'FINANCIAMIENTO DIGITAL' in texto: return 'FINANCIAMIENTO DIGITAL'
    if 'CRED JOVEN' in texto: return 'CREDITO JOVEN'
    if 'GARANTIA AUTOMATICA' in texto: return 'GARANTIA AUTOMATICA'
    if 'GARANTIA AGIL' in texto: return 'GARANTIA AGIL'
    if 'CREDICADENAS' in texto or 'GRANDES EMPRESAS' in texto: return 'CREDICADENAS'
    if 'AUTOTRANSPORTE' in texto: return 'AUTOTRANSPORTE'
    if 'ADQUISICION VEHICULOS' in texto: return 'ADQUISICION VEHICULOS'
    if 'TRADICIONAL' in texto: return 'TRADICIONAL'
    if 'GLOBAL PYME' in texto: return 'GLOBAL PYME'
    if re.search(r'CONSTRUCTOR CREDIACTIVO|CREDIAC EMPR', texto): return 'CREDIACTIVO'
    if 'SELECTIVA' in texto: return 'SELECTIVA'
    if 'FORTALECIMIENTO IFNBS' in texto: return 'FORTALECIMIENTO IFNBS'

    return 'OTROS PROGRAMAS'


# ---------------------------------------------------------------------------
# 4b. Limpieza / normalización de ESTADO
# ---------------------------------------------------------------------------
MAPEO_ESTADOS = {
    "AGS": "AGUASCALIENTES", "AGUASCALIENTES": "AGUASCALIENTES",
    "BC": "BAJA CALIFORNIA", "BAJA CALIFORNIA NORTE": "BAJA CALIFORNIA",
    "BAJA CALIFORNIA": "BAJA CALIFORNIA", "TIJUANA": "BAJA CALIFORNIA",
    "BCS": "BAJA CALIFORNIA SUR", "BAJA CALIFORNIA SUR": "BAJA CALIFORNIA SUR",
    "CAMPECHE": "CAMPECHE",
    "CDMX": "CIUDAD DE MEXICO", "DISTRITO FEDERAL": "CIUDAD DE MEXICO",
    "CIUDAD DE MEXICO": "CIUDAD DE MEXICO", "DF": "CIUDAD DE MEXICO",
    "CHIS": "CHIAPAS", "CHIAPAS": "CHIAPAS",
    "CHIH": "CHIHUAHUA", "CHIHUAHUA": "CHIHUAHUA",
    "COAH": "COAHUILA", "COAHUILA": "COAHUILA", "COAHUILA DE ZARAGOZA": "COAHUILA",
    "COLIMA": "COLIMA",
    "DGO": "DURANGO", "DURANGO": "DURANGO",
    "EDOMEX": "ESTADO DE MEXICO", "EDO MEX": "ESTADO DE MEXICO",
    "EDO DE MEXICO": "ESTADO DE MEXICO", "MEXICO": "ESTADO DE MEXICO",
    "ESTADO DE MEXICO": "ESTADO DE MEXICO",
    "GTO": "GUANAJUATO", "GUANAJUATO": "GUANAJUATO",
    "GRO": "GUERRERO", "GUERRERO": "GUERRERO",
    "HGO": "HIDALGO", "HIDALGO": "HIDALGO",
    "JAL": "JALISCO", "JALISCO": "JALISCO",
    "MICH": "MICHOACAN", "MICHOACAN": "MICHOACAN", "MICHOACAN DE OCAMPO": "MICHOACAN",
    "MOR": "MORELOS", "MORELOS": "MORELOS",
    "NAY": "NAYARIT", "NAYARIT": "NAYARIT", "TEPIC": "NAYARIT",
    "NL": "NUEVO LEON", "NUEVO LEON": "NUEVO LEON",
    "OAX": "OAXACA", "OAXACA": "OAXACA",
    "PUE": "PUEBLA", "PUEBLA": "PUEBLA",
    "QRO": "QUERETARO", "QUERETARO": "QUERETARO",
    "QROO": "QUINTANA ROO", "QUINTANA ROO": "QUINTANA ROO",
    "SLP": "SAN LUIS POTOSI", "SAN LUIS POTOSI": "SAN LUIS POTOSI",
    "SIN": "SINALOA", "SINALOA": "SINALOA",
    "SON": "SONORA", "SONORA": "SONORA", "HERMOSILLO": "SONORA",
    "TAB": "TABASCO", "TABASCO": "TABASCO",
    "TAMPS": "TAMAULIPAS", "TAMAULIPAS": "TAMAULIPAS",
    "TLAX": "TLAXCALA", "TLAXCALA": "TLAXCALA",
    "VER": "VERACRUZ", "VERACRUZ": "VERACRUZ",
    "VERACRUZ DE IGNACIO DE LA LLAVE": "VERACRUZ",
    "YUC": "YUCATAN", "YUCATAN": "YUCATAN",
    "ZAC": "ZACATECAS", "ZACATECAS": "ZACATECAS",
}


def limpiar_estado(texto) -> str:
    if pd.isna(texto):
        return "SIN ESTADO"
    clave = re.sub(r"\s+", " ", str(texto).upper().strip())
    return MAPEO_ESTADOS.get(clave, clave)


# ---------------------------------------------------------------------------
# 4c. Limpieza de INT_RAZON_SOCIAL -> nombres comerciales cortos de bancos
#     (heredada/adaptada del diccionario mapeo_intermediarios de v4, pero
#     expresada como reglas jerárquicas por regex para tolerar variantes de
#     razón social que no estaban en el diccionario original).
# ---------------------------------------------------------------------------
def limpiar_intermediario(texto) -> str:
    if pd.isna(texto):
        return "SIN INTERMEDIARIO"
    t = str(texto).upper()

    if re.search(r'BANORTE|MERCANTIL DEL NORTE', t): return 'BANORTE'
    if re.search(r'BBVA|BANCOMER', t): return 'BBVA'
    if re.search(r'BANAMEX|CITIBANAMEX', t): return 'BANAMEX'
    if 'SANTANDER' in t: return 'SANTANDER'
    if 'BAJIO' in t: return 'BANBAJIO'
    if re.search(r'BANREGIO|REGIONAL DE MONTERREY', t): return 'BANREGIO'
    if re.search(r'VE POR MAS|VEPORMAS', t): return 'VE POR MAS'
    if 'MIFEL' in t: return 'MIFEL'
    if 'AFIRME' in t: return 'AFIRME'
    if 'BANSI' in t: return 'BANSI'
    if 'HSBC' in t: return 'HSBC'
    if 'INVEX' in t: return 'INVEX'
    if re.search(r'SCOTIABANK|INVERLAT', t): return 'SCOTIABANK'
    if 'SABADELL' in t: return 'SABADELL'
    if re.search(r'\bBASE\b', t) and 'BANCO' in t: return 'BANCO BASE'
    if 'MULTIVA' in t: return 'BANCO MULTIVA'
    if 'BANCOPPEL' in t: return 'BANCOPPEL'
    if re.search(r'NACIONAL FINANCIERA|^NAFIN$', t): return 'NAFIN'
    if 'TRATON' in t: return 'TRATON FINANCIAL SERVICES'
    if 'ACE FIANZAS' in t: return 'ACE FIANZAS MONTERREY'
    if 'ASERTA' in t: return 'AFIANZADORA ASERTA'
    if 'INSURGENTES' in t: return 'AFIANZADORA INSURGENTES'
    if 'FIANZAS ATLAS' in t: return 'FIANZAS ATLAS'
    if 'MERCADER' in t: return 'MERCADER FINANCIAL'
    if re.search(r'AHORRO DE ENERGIA|^FIDE$', t): return 'FIDE'
    if 'NR FINANCE' in t: return 'NR FINANCE MEXICO'
    if 'UC GENERAL' in t: return 'UC GENERAL'

    # Fallback: sin match conocido, se depuran prefijos comunes de
    # BANCOMEXT/NAFIN y se conserva la razón social restante.
    limpio = re.sub(r'^(BANCOMEXT|NAFIN)\s*[/\-]?\s*', '', t).strip()
    return limpio if limpio else t


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------
def main() -> None:
    df = cargar_datos()
    df = descartar_y_renombrar(df)
    df = transformar_periodo(df)

    df["programa"] = df["programa_raw"].apply(limpiar_programa)
    df["estado"] = df["estado_raw"].apply(limpiar_estado)
    df["intermediario"] = df["intermediario_raw"].apply(limpiar_intermediario)
    df = df.drop(columns=["programa_raw", "estado_raw", "intermediario_raw"])

    # Tipos numéricos
    df["saldo"] = pd.to_numeric(df["saldo"], errors="coerce")
    df["monto_colocado"] = pd.to_numeric(df["monto_colocado"], errors="coerce")
    df["tasa"] = pd.to_numeric(df["tasa"], errors="coerce")
    df["rfc"] = df["rfc"].astype(str).str.strip().str.upper()

    # Categorías para reducir tamaño y acelerar agrupaciones en DuckDB
    for col in ["intermediario", "programa", "estado", "estrato", "banco"]:
        df[col] = df[col].astype("category")

    # Creamos una columna de partición basada en año y mes
    df["anio_mes"] = df["periodo"].dt.strftime("%Y-%m")

    Path(DIR_SALIDA).mkdir(parents=True, exist_ok=True)
    df.to_parquet(
        DIR_SALIDA,
        index=False,
        engine="pyarrow",
        partition_cols=["anio_mes"]
    )

    print(
        f"Archivo consolidado con {len(df):,} registros provenientes de "
        f"{len(ARCHIVOS_RAW)} archivos parquet."
    )
    if df["periodo"].notna().any():
        print(f"Periodo cubierto: {df['periodo'].min():%Y-%m} a {df['periodo'].max():%Y-%m}")
    print(f"Guardado particionado en: {DIR_SALIDA}")


if __name__ == "__main__":
    main()
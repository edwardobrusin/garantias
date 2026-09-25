"""
data_prep_v5.py

Consolida los 3 parquet crudos del nuevo origen de datos, descarta columnas
innecesarias, renombra a nombres amigables, transforma el periodo YYYYMM a
datetime y aplica la lógica de limpieza heredada de v4 (programa, estado e
intermediario) para dejar un único parquet listo para el dashboard v5.
"""

import re
import shutil
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

    # 1. T-MEC (Debe ir antes que Comercio Exterior general para no solaparse)
    if re.search(r'COMEX T-MEC|COMEX TMEC|COMERCIO EXTERIOR T-MEC|T-MEC PYME|TMEC|T-MEC', texto): return 'COMEX T-MEC'
    
    # 2. Comercio Exterior y Turismo
    if re.search(r'COMEX|COMERCIO EXT|PYMEX|EXPORTADOR|COM EXT', texto): return 'COMERCIO EXTERIOR'
    if re.search(r'TURISMO|HOTEL|EMPRESTUR', texto): return 'TURISMO'

    # 3. Impulso Regional / Reactivación Económica (Programas Estatales)
    if re.search(r'IMPULSO|IMPUSO NAFIN|IMP ECON|IMP ECO\s|IMP PARA EL DESARROLLO|FORT Y CONS MIPYMES|REACTIVACION ECONOMICA|REACT ECON|REAC ECON|PROM DES ECON', texto): return 'IMPULSO REGIONAL Y REACTIVACION'

    # 4. Desastres Naturales y Emergentes
    if re.search(r'DESASTRE|INUNDACION|HURACAN|EMERGENTE', texto): return 'APOYO DESASTRES NATURALES'

    # 5. Sectores Industriales y Específicos
    if re.search(r'AUTOMOTRIZ', texto): return 'PROVEEDORES SECTOR AUTOMOTRIZ'
    if re.search(r'MOLDES.*TROQUELES', texto): return 'MOLDES Y TROQUELES'
    if re.search(r'CUERO Y CALZADO', texto): return 'CUERO Y CALZADO'
    if re.search(r'TEXTIL', texto): return 'TEXTIL, VESTIDO Y MODA'
    if re.search(r'ELECTRICO.*ELECTRON|ELECTRONICO', texto): return 'PROVEEDORES SECTOR ELECTRICO-ELECTRONICO'
    if re.search(r'GASOLINERA', texto): return 'GASOLINERAS'
    if re.search(r'CONSTRUCCION', texto): return 'CONSTRUCCION'
    if re.search(r'RADIODIFUSION', texto): return 'RADIODIFUSION'
    if re.search(r'SECTOR MEDICO', texto): return 'SECTOR MEDICO'
    if re.search(r'UNIV|ESTUDIOS SUP|CENTROS CULTURALES|ESCUELA|TECNOLOGICA', texto): return 'SECTOR EDUCATIVO'
    if re.search(r'VEN A COMER|RESTAURANTES', texto): return 'SECTOR RESTAURANTERO'

    # 6. Transporte, Taxis y Vehículos
    if re.search(r'TRANSPORTE PUBLICO|TAXI', texto): return 'SUSTITUCION TRANSPORTE PUBLICO'
    if re.search(r'SUBASTA|VEHICULOS LIGEROS|ADQUISICION VEHICULOS', texto): return 'ADQUISICION VEHICULOS'
    if re.search(r'AUTOTRANSPORTE|TRANSPORTISTA|SUSTIT.*VEHICULAR', texto): return 'AUTOTRANSPORTE'

    # 7. Mujeres, Jóvenes y Primer Crédito
    if re.search(r'MUJER', texto): return 'MUJERES EMPRESARIAS'
    if re.search(r'CRED JOVEN|CREDITO JOVEN', texto): return 'CREDITO JOVEN'
    if re.search(r'TU PRIMER CR[EÉ]D', texto): return 'TU PRIMER CREDITO'

    # 8. Energía y Vivienda
    if re.search(r'EFICIENCIA ENERGETICA|AHORRO ENERG|SIST SOLARES|FOTOVOLTAICO|ECO CR[EÉ]DITO|FDO SOSTENIBLE|PANEL SOLAR', texto): return 'EFICIENCIA ENERGETICA Y RENOVABLES'
    if re.search(r'MEJORAMIENTO.*VIVIENDA', texto): return 'MEJORAMIENTO DE VIVIENDA'

    # 9. Productos Financieros Específicos NAFIN / BANCOMEXT
    if re.search(r'CREDIACTIVO|CREDIAC|CREDIATIVO', texto): return 'CREDIACTIVO'
    if re.search(r'CAPEX', texto): return 'CAPEX'
    if re.search(r'IFNB|IFNBS', texto): return 'FORTALECIMIENTO IFNBS'
    if re.search(r'FIANZAS PARI PASSU|GTIA SOBRE FIANZAS', texto): return 'GARANTIA SOBRE FIANZAS'
    if re.search(r'CREDISUMINISTROS', texto): return 'CREDISUMINISTROS'
    if re.search(r'CREDICADENAS|EMPRESAS EJE', texto): return 'CREDICADENAS'
    if re.search(r'PLAN MEXICO', texto): return 'PLAN MEXICO'
    if re.search(r'COBERTURAS DIFERENCIADAS', texto): return 'COBERTURAS DIFERENCIADAS'
    if re.search(r'GARANTIA AUTOMATICA', texto): return 'GARANTIA AUTOMATICA'
    if re.search(r'GARANTIA AGIL|PYME AGIL', texto): return 'GARANTIA AGIL'
    if re.search(r'ARRENDAMIENTO', texto): return 'ARRENDAMIENTO FINANCIERO'
    if re.search(r'FINANCIAMIENTO DIGITAL', texto): return 'FINANCIAMIENTO DIGITAL'
    if re.search(r'GOBIERNO FEDERAL', texto): return 'PROVEEDOR DEL GOBIERNO FEDERAL'
    if re.search(r'SELECTIVA|SELECT\s', texto): return 'SELECTIVA'
    if re.search(r'PRODUCTO NAFIN EMPRESARIAL', texto): return 'PRODUCTO NAFIN EMPRESARIAL'

    # 10. Categorías por Tamaño / Genéricas (Catch-All final)
    if re.search(r'MICROEMPRESA|MICRONEGOCIO|MICROEMP|MICROAPOYO', texto): return 'FINANCIAMIENTO A MICRONEGOCIOS'
    if re.search(r'DIVISION EMPRESARIAL.*GDE|EMPRESA MEDIANA Y GRANDE|GRANDES EMPRESAS|MEDIANA EMPRESA', texto): return 'GRANDES EMPRESAS Y CORPORATIVO'
    if re.search(r'PYME|CREDIPYME|CREDITO SIMPLE|CRED SIMPLE|SIMPLE SUB|SEMIPAR|CREDITO EMPRESARIAL|CREDITO A EMPRESAS|CRED LIQUIDO|CAP TRAB|TRADICIONAL|TRAD HASTA|LINEAS PP|CONSOLIDACIONES|MIPYME|CREDITO COMERCIAL|PRODUCTO MIFEL', texto): return 'CREDITO PYME TRADICIONAL'

    # Si sobrevive a todo lo anterior, se clasifica como Otros
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

    # Limpiamos el directorio previo para evitar acumular parquets viejos o duplicar datos
    if Path(DIR_SALIDA).exists():
        shutil.rmtree(DIR_SALIDA)

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
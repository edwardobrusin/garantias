"""
clean_acreditados.py

Lee DATOS.parquet, transforma la columna de fecha y particiona 
los datos por año y mes.
"""

import re
import shutil
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
ARCHIVO_RAW = "data/raw/DATOS.parquet"
DIR_SALIDA = "data/intermediate/acreditados_part"

# ---------------------------------------------------------------------------
# Diccionarios y Funciones de limpieza
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
# Orquestación
# ---------------------------------------------------------------------------
def main() -> None:
    # 1. Cargar datos
    print(f"Cargando {ARCHIVO_RAW}...")
    df = pd.read_parquet(ARCHIVO_RAW)
    df.columns = df.columns.str.strip()

    # 1.5 Limpiar estados
    col_estado = "Estado (Acre)"
    if col_estado in df.columns:
        df["estado"] = df[col_estado].apply(limpiar_estado)
        df["estado"] = df["estado"].astype("category")
    else:
        print(f"Advertencia: No se encontró la columna '{col_estado}'")

    # 2. Transformar periodo
    col_fecha = "Fecha o Rango de Consulta (MA)"
    if col_fecha not in df.columns:
        raise KeyError(f"La columna '{col_fecha}' no se encuentra en el dataframe.")

    df["periodo"] = pd.to_datetime(
        df[col_fecha].astype("Int64").astype(str),
        format="%Y%m",
        errors="coerce",
    )

    # Creamos una columna de partición basada en año y mes
    df["anio_mes"] = df["periodo"].dt.strftime("%Y-%m")

    # 3. Limpieza de directorio y exportación particionada
    if Path(DIR_SALIDA).exists():
        shutil.rmtree(DIR_SALIDA)

    Path(DIR_SALIDA).mkdir(parents=True, exist_ok=True)
    
    print(f"Guardando archivo particionado en: {DIR_SALIDA}...")
    df.to_parquet(
        DIR_SALIDA,
        index=False,
        engine="pyarrow",
        partition_cols=["anio_mes"]
    )

    print(f"Proceso completado. {len(df):,} registros guardados.")
    if df["periodo"].notna().any():
        print(f"Periodo cubierto: {df['periodo'].min():%Y-%m} a {df['periodo'].max():%Y-%m}")

if __name__ == "__main__":
    main()


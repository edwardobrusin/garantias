import os
import warnings
from pathlib import Path
import pandas as pd
import pyodbc

# Suprimir advertencias de pandas sobre conexiones pyodbc directas
warnings.filterwarnings("ignore", category=UserWarning)


def mdb_a_parquet(ruta_mdb: Path, directorio_salida: Path) -> None:
    directorio_salida.mkdir(parents=True, exist_ok=True)
    
    ruta_absoluta_mdb = ruta_mdb.resolve()
    nombre_base = ruta_mdb.stem

    conn_str = (
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={ruta_absoluta_mdb};"
    )

    conn = None
    try:
        print(f"Conectando a {ruta_absoluta_mdb}...")
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Extraer tablas de usuario
        tablas = [table.table_name for table in cursor.tables(tableType="TABLE")]
        print(f"Se encontraron {len(tablas)} tabla(s): {tablas}")

        for tabla in tablas:
            print(f"Procesando tabla: [{tabla}]...")
            query = f"SELECT * FROM [{tabla}]"
            df = pd.read_sql(query, conn)

            ruta_parquet = directorio_salida / f"{nombre_base}.parquet"
            df.to_parquet(ruta_parquet, engine="pyarrow", index=False)
            print(f" ✓ Guardado exitosamente: {ruta_parquet}\n")

    except pyodbc.Error as e:
        print(f"Error ODBC al procesar {ruta_mdb.name}: {e}\n")
    except Exception as e:
        print(f"Error inesperado al procesar {ruta_mdb.name}: {e}\n")
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    # Raíz del proyecto (un nivel arriba de scripts/)
    base_dir = Path(__file__).resolve().parent.parent

    # data/raw contiene los .mdb de entrada y los .parquet de salida
    carpeta_origen = base_dir / "data" / "raw"
    carpeta_destino = base_dir / "data" / "raw"

    # Procesar EXPORT_21.mdb hasta EXPORT_26.mdb
    for anio in range(21, 27):
        archivo_origen = carpeta_origen / f"EXPORT_{anio}.mdb"

        if archivo_origen.is_file():
            print(f"=== Procesando: {archivo_origen.name} ===")
            mdb_a_parquet(archivo_origen, carpeta_destino)
        else:
            print(f"⚠ Archivo omitido (no encontrado): {archivo_origen.name}")
import pandas as pd
import numpy as np
import re
from pathlib import Path

# Rutas de entrada y salida
ruta_excel = "data/raw/Garantías 2025_2026.xlsx"
ruta_parquet = "data/intermediate/garantias.parquet"

# Cargar el archivo sin leer los datos aún para obtener los nombres de las hojas
xls = pd.ExcelFile(ruta_excel)
hojas_disponibles = xls.sheet_names 

dataframes = []

# Iterar dinámicamente sobre cualquier hoja que exista en el archivo
for hoja in hojas_disponibles:
    # Leer la hoja actual
    df_temporal = pd.read_excel(xls, sheet_name=hoja)
    
    # Agregar el nombre de la hoja como metadato para no perder el corte temporal
    df_temporal['Periodo_Corte'] = hoja
    
    dataframes.append(df_temporal)

# Consolidar todas las hojas en un solo DataFrame
df_consolidado = pd.concat(dataframes, ignore_index=True)

# Diccionario para limpiar y estandarizar la columna "Nombre Intermediario"
mapeo_intermediarios = {
    # Banorte
    "BANCO MERCANTIL DEL NORTE": "BANORTE",
    "BANCOMEXT-BANORTE": "BANORTE",
    
    # BBVA
    "BBV BANCOMER": "BBVA",
    "BANCOMEXT BBVA BANCOMER": "BBVA",
    
    # Banamex
    "BANAMEX": "BANAMEX",
    "BANCOMEXTBANAMEX": "BANAMEX",
    
    # Santander
    "BANCO SANTANDER": "SANTANDER",
    "BANCOMEXT-SANTANDER": "SANTANDER",
    
    # Banbajío
    "BANCO DEL BAJIO": "BANBAJIO",
    "BANCOMEXT/BAJIO": "BANBAJIO",
    "FINANCIERA BAJIO SA DE CV": "BANBAJIO",
    
    # Banregio
    "BANCO REGIONAL DE MONTERREY": "BANREGIO",
    "BANCOMEXT/BANCO REGIONAL DE MONTERREY": "BANREGIO",
    "AF BANREGIO (SOFOM)": "BANREGIO",
    
    # Ve por Más
    "BANCO VE POR MAS": "VE POR MAS",
    "BANCOMEXT/ VE POR MAS": "VE POR MAS",
    "NAFIN/BANCO VE POR MAS": "VE POR MAS",
    
    # Mifel
    "BANCA MIFEL": "MIFEL",
    "BANCOMEXT MIFEL": "MIFEL",
    
    # Afirme
    "BANCA AFIRME": "AFIRME",
    "BANCOMEXTBANCA AFIRME": "AFIRME",
    
    # Bansí
    "BANSI SA": "BANSI",
    "BANCOMEXT / BANSI": "BANSI",
    
    # HSBC
    "HSBC MEXICO": "HSBC",
    "BANCOMEXTHSBC": "HSBC",
    
    # Invex y Scotiabank (Inverlat)
    "NAFIN / BANCO INVEX, S.A.": "INVEX",
    "BANCO INVERLAT MEXICO BROKER": "SCOTIABANK",
    "SCOTIABANK INVERLAT SA F PENSIONES VERACRUZ": "SCOTIABANK",
    
    # Otros bancos 
    "BANCOMEXT/BANCO BASE S.A.": "BANCO BASE",
    "BANCOMEXT/BANCO SABADELL, S.A., I.B.M.": "BANCO SABADELL",
    "BANCO MULTIVA SA DE CV": "BANCO MULTIVA",
    "BANCOPPEL SA INSTITUCION DE BANCA MULTIPLE": "BANCOPPEL",
    
    # Entidades no bancarias, aseguradoras y financieras
    "BANCOMEXT/TRATON FINANCIAL SERVICES MEXICO": "TRATON FINANCIAL SERVICES",
    "TRATON FINANCIAL SERVICES MEXICO": "TRATON FINANCIAL SERVICES",
    "ACE FIANZAS MONTERREY S.A.": "ACE FIANZAS MONTERREY",
    "AFIANZADORA ASERTA SA DE CV GRUPO FINANCIERO ASERTA": "AFIANZADORA ASERTA",
    "AFIANZADORA INSURGENTES SA": "AFIANZADORA INSURGENTES",
    "FIANZAS ATLAS SA": "FIANZAS ATLAS",
    "MERCADER FINANCIAL": "MERCADER FINANCIAL",
    "FIDEICOMISO PARA EL AHORRO DE ENERGIA ELECTRICA": "FIDE",
    "NR FINANCE MEXICO SA DE CV SOFOM ENR": "NR FINANCE MEXICO",
    "UC GENERAL SA CV": "UC GENERAL",
    "NACIONAL FINANCIERA": "NAFIN"
}

# Aplicar el reemplazo al dataframe y eliminar espacios en blanco residuales
df_consolidado['Nombre Intermediario'] = df_consolidado['Nombre Intermediario'].replace(mapeo_intermediarios).str.strip()

# 1. Función jerárquica para extraer el Programa Limpio
def limpiar_programa(texto):
    texto = str(texto).upper()
    
    # Ejes principales de NAFIN
    if re.search(r'IMPULSO NAFIN|IMPUSO NAFIN|IMPULSO MIPYMES', texto): return 'IMPULSO NAFIN'
    if 'PRODUCTO NAFIN EMPRESARIAL' in texto: return 'PRODUCTO NAFIN EMPRESARIAL'
    
    # Programas sectoriales y específicos
    if re.search(r'COMEX T-MEC|COMEX TMEC|COMERCIO EXTERIOR T-MEC|COMERCIO EXTERIOR EMPRESARIAL|PROGRAMA T-MEC|T-MEC PYME|TMEC', texto): return 'COMEX T-MEC'
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

# 2. Diccionario de estados explícitos y municipios clave
mapeo_estados = {
    'AGUASCALIENTES': 'AGUASCALIENTES', 'BAJA CALIFORNIA NORTE': 'BAJA CALIFORNIA', 
    'BAJA CALIFORNIA SUR': 'BAJA CALIFORNIA SUR', 'TIJUANA': 'BAJA CALIFORNIA',
    'CAMPECHE': 'CAMPECHE', 'CDMX': 'CIUDAD DE MEXICO', 'CHIAPAS': 'CHIAPAS', 'CHIS': 'CHIAPAS',
    'CHIHUAHUA': 'CHIHUAHUA', 'COAHUILA': 'COAHUILA', 'COLIMA': 'COLIMA', 'DURANGO': 'DURANGO',
    'EDO MEX': 'ESTADO DE MEXICO', 'EDO DE MEXICO': 'ESTADO DE MEXICO', 'GUANAJUATO': 'GUANAJUATO',
    'GUERRERO': 'GUERRERO', 'GRO': 'GUERRERO', 'HIDALGO': 'HIDALGO', 'JALISCO': 'JALISCO',
    'MICHOACAN': 'MICHOACAN', 'MORELOS': 'MORELOS', 'TEPIC': 'NAYARIT', 'NUEVO LEON': 'NUEVO LEON',
    'OAXACA': 'OAXACA', 'OAX': 'OAXACA', 'PUEBLA': 'PUEBLA', 'QUERETARO': 'QUERETARO',
    'QUINTANA ROO': 'QUINTANA ROO', 'SAN LUIS POTOSI': 'SAN LUIS POTOSI', 'SINALOA': 'SINALOA',
    'SONORA': 'SONORA', 'HERMOSILLO': 'SONORA', 'TABASCO': 'TABASCO', 'TAMAULIPAS': 'TAMAULIPAS',
    'VERACRUZ': 'VERACRUZ', 'YUCATAN': 'YUCATAN', 'ZACATECAS': 'ZACATECAS'
}

def extraer_estado(row):
    texto = str(row['Programa']).upper()
    estado_original = str(row['Estado']).upper().strip()
    
    # 1. Si el estado original (o su abreviatura) ya es parte del nombre del programa, se respeta
    claves_estado_original = [k for k, v in mapeo_estados.items() if v == estado_original]
    for clave in claves_estado_original:
        if re.search(rf'\b{clave}\b', texto):
            return estado_original
            
    # 2. Si no, extrae el primer estado que haga match
    for clave in sorted(mapeo_estados.keys(), key=len, reverse=True):
        if re.search(rf'\b{clave}\b', texto):
            return mapeo_estados[clave]
    return None

# Normalizar la columna original de Estado primero para usarla en la función de extracción
df_consolidado['Estado'] = df_consolidado['Estado'].astype(str).str.upper().str.strip()

# Homologar estados residuales directamente en la columna base
correccion_estados = {
    'BAJA CALIFORNIA NORTE': 'BAJA CALIFORNIA',
    'MEXICO': 'ESTADO DE MEXICO'
}
df_consolidado['Estado'] = df_consolidado['Estado'].replace(correccion_estados)

# Aplicar las funciones a la base consolidada
df_consolidado['Programa_Limpio'] = df_consolidado['Programa'].apply(limpiar_programa)
df_consolidado['Estado_Extraido'] = df_consolidado.apply(extraer_estado, axis=1)

# 3. Lógica condicionada para generar Estado_v2 de forma vectorizada
df_consolidado['Estado_v2'] = np.where(
    df_consolidado['Estado_Extraido'].notna() & (df_consolidado['Estado_Extraido'] != df_consolidado['Estado']),
    df_consolidado['Estado_Extraido'],
    df_consolidado['Estado']
)

# Limpiar columnas temporales y optimizar tipos de datos a 'category'
df_consolidado = df_consolidado.drop(columns=['Estado_Extraido'])

# Eliminar espacios residuales en los nombres de todas las columnas
df_consolidado.columns = df_consolidado.columns.str.strip()

# Diccionario para mapear fechas en español a un formato numérico estandarizado
meses_es = {
    ' de enero de ': '/01/', ' de febrero de ': '/02/', ' de marzo de ': '/03/',
    ' de abril de ': '/04/', ' de mayo de ': '/05/', ' de junio de ': '/06/',
    ' de julio de ': '/07/', ' de agosto de ': '/08/', ' de septiembre de ': '/09/',
    ' de octubre de ': '/10/', ' de noviembre de ': '/11/', ' de diciembre de ': '/12/'
}

# Conversión estricta de fechas a formato datetime (asigna NaT a errores/vacíos)
for col in ['Fecha Apertura', 'Fecha Registro']:
    serie_temporal = df_consolidado[col].astype(str).str.lower()
    for mes, reemplazo in meses_es.items():
        serie_temporal = serie_temporal.str.replace(mes, reemplazo, regex=False)
    df_consolidado[col] = pd.to_datetime(serie_temporal, format='%d/%m/%Y', errors='coerce')

# Homologar la columna Tasa para evitar conflictos de tipos
df_consolidado['Tasa'] = df_consolidado['Tasa'].astype(str).str.strip()

for col in ['Nombre Intermediario', 'Programa_Limpio', 'Estado_v2', 'Tasa']:
    df_consolidado[col] = df_consolidado[col].astype('category')

# Crear el directorio de salida si no existe
Path(ruta_parquet).parent.mkdir(parents=True, exist_ok=True)

# Exportar a formato Parquet
df_consolidado.to_parquet(ruta_parquet, index=False, engine='pyarrow')

print(f"Archivo consolidado con {len(df_consolidado)} registros provenientes de {len(hojas_disponibles)} hojas.")
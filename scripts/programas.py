import pandas as pd
import re

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

def main():
    archivos_raw = [
        "data/raw/garantias24_0926.parquet",
        "data/raw/garantias25_0926.parquet",
        "data/raw/garantias26_0926.parquet",
    ]
    
    print("Cargando datos crudos...")
    dfs = [pd.read_parquet(ruta, columns=['PROGRAMA_DESCRIPCION']) for ruta in archivos_raw]
    df_completo = pd.concat(dfs, ignore_index=True)
    
    print("Aplicando reglas de limpieza...")
    df_completo['Programa_Limpio'] = df_completo['PROGRAMA_DESCRIPCION'].apply(limpiar_programa)
    
    # Filtrar solo los que cayeron en "OTROS PROGRAMAS"
    df_otros = df_completo[df_completo['Programa_Limpio'] == 'OTROS PROGRAMAS']
    
    # Contar las frecuencias de los nombres crudos originales
    frecuencias = df_otros['PROGRAMA_DESCRIPCION'].value_counts().reset_index()
    frecuencias.columns = ['Programa Crudo Original', 'Frecuencia']
    
    # Exportar a CSV
    frecuencias.to_csv("programas_no_clasificados.csv", index=False, encoding="utf-8-sig")
    
    print(f"\nResumen:")
    print(f"Total de registros evaluados: {len(df_completo):,}")
    print(f"Registros clasificados como 'OTROS PROGRAMAS': {len(df_otros):,}")
    print(f"Programas únicos no clasificados: {len(frecuencias):,}")
    print("\nTop 15 programas que no están siendo atrapados:")
    print(frecuencias.head(15).to_string(index=False))
    print("\n¡Archivo 'programas_no_clasificados.csv' generado con éxito!")

if __name__ == "__main__":
    main()
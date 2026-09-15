import streamlit as st

# ==========================================
# ⚙️ CONFIGURACIÓN DE VERSIÓN
# Solo modifica esta variable para apuntar 
# al archivo de la versión que quieres mostrar
# ==========================================
VERSION_ACTUAL = "dash_v2.py"


# ==========================================
# 🚀 EJECUCIÓN (No tocar)
# ==========================================
try:
    with open(VERSION_ACTUAL, "r", encoding="utf-8") as file:
        codigo = file.read()
        # Ejecuta el código en el contexto global actual
        exec(codigo, globals())
        
except FileNotFoundError:
    st.error(f"🚨 No se encontró el archivo: `{VERSION_ACTUAL}`")
    st.info("Por favor, verifica que el nombre sea correcto y esté en la misma carpeta que `app.py`.")
except Exception as e:
    st.error(f"🚨 Ocurrió un error al ejecutar `{VERSION_ACTUAL}`:")
    st.exception(e)
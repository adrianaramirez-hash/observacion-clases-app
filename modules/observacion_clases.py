import streamlit as st
import pandas as pd

def pagina_observacion_clases():
    """
    Página principal del módulo de Observación de clases.

    De momento es una versión sencilla:
    - Muestra un título y una explicación.
    - Permite subir un archivo (Excel o CSV) con las observaciones.
    - Muestra una tabla con las primeras filas del archivo.
    Más adelante podemos volver a agregar gráficos, filtros, etc.
    """

    st.title("Observación de clases")

    st.markdown(
        """
        Esta es la vista de **Observación de clases**.

        Por ahora, puedes:
        - Subir un archivo con las observaciones (Excel o CSV).
        - Ver una vista rápida de los datos cargados.

        Más adelante volveremos a construir:
        - Indicadores por corte.
        - Gráficas.
        - Tablas de detalle por docente, grupo, etc.
        """
    )

    # --- Carga de archivo ---
    archivo = st.file_uploader(
        "Sube el archivo de observaciones (Excel o CSV)",
        type=["xlsx", "xls", "csv"]
    )

    if not archivo:
        st.info("Sube un archivo para ver los datos.")
        return

    # Intentamos leer el archivo según la extensión
    try:
        nombre = archivo.name.lower()
        if nombre.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
    except Exception as e:
        st.error(f"No se pudo leer el archivo. Revisa el formato. Detalle técnico: {e}")
        return

    if df.empty:
        st.warning("El archivo se cargó correctamente, pero no tiene filas.")
        return

    st.subheader("Vista previa de los datos cargados")
    st.dataframe(df.head(50))

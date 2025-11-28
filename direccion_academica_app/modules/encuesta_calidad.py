import streamlit as st

def pagina_encuesta_calidad():
    """
    Módulo de Encuesta de calidad.
    De momento es solo el esqueleto; luego le pegaremos los dashboards reales.
    """
    st.subheader("Encuesta de calidad")

    st.info(
        "Aquí se mostrarán los resultados de la encuesta de calidad.\n\n"
        "En el siguiente paso conectaremos este módulo a tu Google Sheets "
        "de **02_Encuesta_de_calidad** y construiremos las gráficas."
    )

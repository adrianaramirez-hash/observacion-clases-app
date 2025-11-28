import streamlit as st
from modules.observacion_clases import pagina_observacion_clases

st.set_page_config(
    page_title="Dirección Académica UDL",
    layout="wide"
)

MENU = [
    "Observación de clases",
    "Encuesta de calidad",
    "Evaluación docente",
    "Capacitación",
    "Índice de reprobación",
    "Titulación",
    "CENEVAL",
]

def main():
    # LOGO
    st.image("direccion_academica_app/assets/udl_logo.png", use_column_width=True)

    # TÍTULO
    st.markdown(
        "<h2 style='text-align:center; margin-top:0;'>Dirección Académica</h2>",
        unsafe_allow_html=True
    )
    st.markdown("---")

    # MENÚ
    opcion = st.selectbox("Selecciona un módulo:", MENU)

    # NAVEGACIÓN
    if opcion == "Observación de clases":
        pagina_observacion_clases()
    else:
        st.info(f"El módulo **{opcion}** aún no está configurado.")

if __name__ == "__main__":
    main()

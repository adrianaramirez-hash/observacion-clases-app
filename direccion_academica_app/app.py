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
    # Encabezado con logo centrado y tamaño controlado
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(
            "direccion_academica_app/assets/udl_logo.png",
            width=320  # 👈 AJUSTA AQUÍ EL TAMAÑO (ej. 250, 300, 400...)
        )
        st.markdown(
            "<h2 style='text-align:center; margin-top:0;'>Dirección Académica</h2>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # Menú principal
    opcion = st.selectbox("Selecciona un módulo:", MENU)

    # Navegación por módulos
    if opcion == "Observación de clases":
        pagina_observacion_clases()
    else:
        st.info(f"El módulo **{opcion}** aún no está configurado.")

if __name__ == "__main__":
    main()


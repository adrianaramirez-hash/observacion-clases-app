import streamlit as st
from modules.observacion_clases import pagina_observacion_clases
from modules.encuesta_calidad import pagina_encuesta_calidad

# Configuración general de la página
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
    # ===== Encabezado: logo a la izquierda, texto a la derecha =====
    col_logo, col_spacer, col_title = st.columns([1, 1, 3])

    with col_logo:
        st.image(
            "direccion_academica_app/assets/udl_logo.png",
            width=180,  # ajusta el tamaño si quieres
        )

    with col_title:
        st.markdown(
            """
            <h1 style='margin-top:1.5rem; margin-bottom:0;'>
                Dirección Académica
            </h1>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ===== Menú principal =====
    opcion = st.selectbox("Selecciona un módulo:", MENU)

    # ===== Navegación por módulos =====
    if opcion == "Observación de clases":
        pagina_observacion_clases()
    elif opcion == "Encuesta de calidad":
        pagina_encuesta_calidad()
    else:
        st.info(f"El módulo **{opcion}** aún no está configurado.")

if __name__ == "__main__":
    main()


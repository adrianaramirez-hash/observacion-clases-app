import streamlit as st

from modules.observacion_clases import pagina_observacion_clases
from modules.encuesta_calidad import pagina_encuesta_calidad

# ---------------------------------------------
# Configuración general de la página
# ---------------------------------------------
st.set_page_config(
    page_title="Dirección Académica UDL",
    layout="wide"
)

MENU = [
    "Observación de clases",
    "Encuesta de calidad",
    # los demás módulos los dejamos para después
    # "Evaluación docente",
    # "Capacitación",
    # "Índice de reprobación",
    # "Titulación",
    # "CENEVAL",
]


def dibujar_encabezado():
    col_logo, col_spacer, col_title = st.columns([1, 1, 3])

    with col_logo:
        # Usa la ruta que ya te funcionaba
        st.image(
            "direccion_academica_app/assets/udl_logo.png",
            width=180,
        )

    with col_title:
        st.markdown(
            """
            <h1 style="margin-top:1.5rem; margin-bottom:0;">
                Dirección Académica
            </h1>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")


def main():
    dibujar_encabezado()

    opcion = st.selectbox("Selecciona un módulo:", MENU)

    if opcion == "Observación de clases":
        pagina_observacion_clases()
    elif opcion == "Encuesta de calidad":
        pagina_encuesta_calidad()
    else:
        st.info(f"El módulo **{opcion}** aún no está configurado.")


if __name__ == "__main__":
    main()

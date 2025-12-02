import streamlit as st

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

def mostrar_encabezado():
    """Encabezado con logo y título."""
    col_logo, col_spacer, col_title = st.columns([1, 1, 3])

    with col_logo:
        # Ajusta esta ruta si hiciera falta
        st.image(
            "assets/udl_logo.png",
            width=180,
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


# ==========================
# CARGA DE MÓDULOS CON TRY
# ==========================

def mostrar_observacion_clases():
    """Intenta cargar la página de Observación de clases."""
    try:
        from modules.observacion_clases import pagina_observacion_clases
        pagina_observacion_clases()
    except Exception as e:
        st.error("No se pudo cargar el módulo **Observación de clases**.")
        st.write(
            "Revisa que exista el archivo "
            "`modules/observacion_clases.py` "
            "y que dentro tenga definida la función `pagina_observacion_clases()`."
        )
        st.exception(e)


def mostrar_encuesta_calidad():
    """Intenta cargar la página de Encuesta de calidad."""
    try:
        from modules.encuesta_calidad import pagina_encuesta_calidad
        pagina_encuesta_calidad()
    except Exception as e:
        st.error("No se pudo cargar el módulo **Encuesta de calidad**.")
        st.write(
            "Revisa que exista el archivo "
            "`modules/encuesta_calidad.py` "
            "y que dentro tenga definida la función `pagina_encuesta_calidad()`."
        )
        st.exception(e)


def main():
    mostrar_encabezado()

    opcion = st.selectbox("Selecciona un módulo:", MENU)

    if opcion == "Observación de clases":
        mostrar_observacion_clases()

    elif opcion == "Encuesta de calidad":
        mostrar_encuesta_calidad()

    else:
        st.info(f"El módulo **{opcion}** aún no está configurado.")


if __name__ == "__main__":
    main()

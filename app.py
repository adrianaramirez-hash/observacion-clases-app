import streamlit as st

# -------------------------------------------------------
# Configuración general de la página
# -------------------------------------------------------
st.set_page_config(
    page_title="Dirección Académica UDL",
    layout="wide"
)

# Menú principal (lo iremos conectando poco a poco)
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
    # ================= ENCABEZADO =================
    col_logo, col_title = st.columns([1, 3])

    with col_logo:
        # IMPORTANTE: el logo está en /assets/udl_logo.png
        st.image("assets/udl_logo.png", width=180)

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

    # ================= MENÚ PRINCIPAL =================
    opcion = st.selectbox("Selecciona un módulo:", MENU)

    # ================= NAVEGACIÓN POR MÓDULOS =================
    if opcion == "Observación de clases":
        mostrar_observacion_clases()

    elif opcion == "Encuesta de calidad":
        mostrar_encuesta_calidad()

    else:
        # Placeholders para módulos que iremos construyendo
        st.info(f"El módulo **{opcion}** aún no está configurado.")


# -------------------------------------------------------
# Vistas / módulos (por ahora solo placeholders)
# -------------------------------------------------------

def mostrar_observacion_clases():
    """
    Aquí conectaremos más adelante tu app de Observación de clases
    (la que ya funciona con Google Sheets).
    De momento dejamos un mensaje para que la app no truene.
    """
    st.subheader("Módulo: Observación de clases")
    st.success("El módulo de Observación de clases se integrará aquí. ✅")


def mostrar_encuesta_calidad():
    """
    Aquí conectaremos después el módulo grande de Encuesta de calidad
    (los 3 formularios, vistas Rectoría / Dirección Académica / Director).
    """
    st.subheader("Módulo: Encuesta de calidad")
    st.info("El módulo de Encuesta de calidad está en construcción. 🔧")


# -------------------------------------------------------
# Punto de entrada
# -------------------------------------------------------
if __name__ == "__main__":
    main()

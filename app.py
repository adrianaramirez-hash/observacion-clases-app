import streamlit as st
from modules.observacion_clases import pagina_observacion_clases

# -------------------------------------------------------
# Configuración general de la página
# -------------------------------------------------------
st.set_page_config(
    page_title="Dirección Académica UDL",
    layout="wide"
)

# Menú principal
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
        st.info(f"El módulo **{opcion}** aún no está configurado.")


# -------------------------------------------------------
# Vistas / módulos
# -------------------------------------------------------
def mostrar_observacion_clases():
    # Aquí simplemente llamamos a la página del módulo
    pagina_observacion_clases()


def mostrar_encuesta_calidad():
    st.subheader("Módulo: Encuesta de calidad")
    st.info("El módulo de Encuesta de calidad está en construcción. 🔧")


# -------------------------------------------------------
# Punto de entrada
# -------------------------------------------------------
if __name__ == "__main__":
    main()

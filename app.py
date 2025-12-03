import streamlit as st
from modules.observacion_clases import pagina_observacion_clases

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

def mostrar_observacion_clases():
    pagina_observacion_clases()


def mostrar_en_construccion(nombre_modulo: str):
    """Muestra un mensaje base para módulos aún no desarrollados."""
    st.header(nombre_modulo)
    st.warning(
        "Próximamente podrás trabajar esta sección. Usa este espacio para agregar "
        "formularios, reportes y gráficas a medida que el ecosistema evolucione."
    )

def main():
    # ===== Encabezado: logo a la izquierda, texto a la derecha =====
    col_logo, col_spacer, col_title = st.columns([1, 1, 3])

    with col_logo:
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

    # ===== Menú principal =====
    opcion = st.selectbox("Selecciona un módulo:", MENU)

    # ===== Navegación por módulos =====
    if opcion == "Observación de clases":
        mostrar_observacion_clases()
    else:
        mostrar_en_construccion(opcion)

if __name__ == "__main__":
    main()

import streamlit as st

# --------------------------------------------------------
# Configuración básica de la app
# --------------------------------------------------------
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

# --------------------------------------------------------
# App principal
# --------------------------------------------------------
def main():
    # Encabezado simple (luego volvemos a poner el logo bonito)
    st.markdown(
        "<h1 style='margin-top: 0.5rem; margin-bottom: 0.5rem;'>Dirección Académica</h1>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Menú principal del ecosistema
    opcion = st.selectbox("Selecciona un módulo:", MENU)

    # Por ahora solo mostramos mensajes de placeholder
    if opcion == "Observación de clases":
        st.info("Aquí se conectará tu módulo ya existente de *Observación de clases*.")
    elif opcion == "Encuesta de calidad":
        st.info("Aquí construiremos el módulo de *Encuesta de calidad* con las vistas Rectoría / Dirección / Director.")
    else:
        st.info(f"El módulo **{opcion}** se agregará más adelante en el ecosistema.")

if __name__ == "__main__":
    main()

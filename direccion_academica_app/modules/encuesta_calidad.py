import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# CONFIGURACIÓN PARA GOOGLE SHEETS
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


@st.cache_data(ttl=60)
def cargar_encuesta_calidad():
    """
    Carga las hojas de respuestas de la Encuesta de calidad
    (varios formularios en varias hojas) y las combina
    en un solo DataFrame.
    """

    # 1) Credenciales desde secrets (igual que en observación de clases)
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)

    # 2) URL DEL GOOGLE SHEETS DE ENCUESTA DE CALIDAD
    SPREADSHEET_URL = (
        "https://docs.google.com/spreadsheets/d/1WAk0Jv42MIyn0iImsAT2YuCsC8-YphKnFxgJYQZKjqU"
    )

    sh = client.open_by_url(SPREADSHEET_URL)

    # 3) Nombres de las hojas con respuestas de los 3 formularios
    nombres_hojas = [
        "servicios virtual y mixto virtual",
        "servicios escolarizados y licenciaturas ejecutivas 2025",
        "Preparatoria 2025",
    ]

    dfs = []
    for nombre in nombres_hojas:
        try:
            ws = sh.worksheet(nombre)
            datos = ws.get_all_records()
            if datos:
                df_tmp = pd.DataFrame(datos)
                # opcional: saber de qué formulario viene cada respuesta
                df_tmp["__origen_hoja__"] = nombre
                dfs.append(df_tmp)
        except gspread.WorksheetNotFound:
            # Si alguna hoja no existe, la ignoramos
            continue

    if not dfs:
        # Si no pudimos leer ninguna hoja, devolvemos DF vacío
        return pd.DataFrame()

    # Unimos todas las respuestas
    df = pd.concat(dfs, ignore_index=True, sort=False)
    return df


# --------------------------------------------------
# PÁGINA DEL MÓDULO: ENCUESTA DE CALIDAD
# --------------------------------------------------


def pagina_encuesta_calidad():
    """
    Módulo de Encuesta de calidad.
    Carga datos, muestra KPIs básicos y la tabla completa.
    """

    st.subheader("Encuesta de calidad")

    # Cargar datos
    try:
        df = cargar_encuesta_calidad()
    except Exception as e:
        st.error("⚠️ Error técnico al cargar la encuesta de calidad:")
        # mostramos el mensaje crudo del error para poder diagnosticar
        st.code(str(e))
        return

    if df.empty:
        st.warning("No se encontraron respuestas en las hojas configuradas.")
        return

    # --------------------------------------------------
    # Limpieza mínima / preparación
    # --------------------------------------------------

    # Intentar convertir alguna columna a fecha si existe
    col_fecha = None
    for posible in ["Fecha", "Marca temporal", "Timestamp"]:
        if posible in df.columns:
            col_fecha = posible
            df[posible] = pd.to_datetime(df[posible], errors="coerce")
            break

    # Intentar identificar una columna de servicio / programa
    col_servicio = None
    for posible in ["Indica el servicio", "Servicio", "Programa", "Carrera"]:
        if posible in df.columns:
            col_servicio = posible
            break

    # --------------------------------------------------
    # KPIs básicos
    # --------------------------------------------------

    total_respuestas = len(df)

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)

    with col_kpi1:
        st.metric("Respuestas totales", total_respuestas)

    with col_kpi2:
        if col_fecha:
            fecha_min = df[col_fecha].min()
            fecha_max = df[col_fecha].max()
            if pd.notna(fecha_min) and pd.notna(fecha_max):
                rango = f"{fecha_min.date()} – {fecha_max.date()}"
            else:
                rango = "N/D"
            st.metric("Rango de fechas", rango)
        else:
            st.metric("Rango de fechas", "Sin columna de fecha")

    with col_kpi3:
        if col_servicio:
            n_servicios = df[col_servicio].nunique()
            st.metric("Servicios / programas", n_servicios)
        else:
            st.metric("Servicios / programas", "No identificado")

    st.markdown("---")

    # --------------------------------------------------
    # Tabla de respuestas
    # --------------------------------------------------

    st.subheader("Respuestas de la encuesta (3 formularios combinados)")

    st.dataframe(df, use_container_width=True)

    st.info(
        "✅ El módulo de Encuesta de calidad ya está conectado a las tres hojas "
        "de respuestas.\n\n"
        "En el siguiente paso podemos definir qué indicadores quieres ver "
        "(satisfacción general, por servicio, por nivel educativo, etc.) "
        "y construir las gráficas correspondientes."
    )


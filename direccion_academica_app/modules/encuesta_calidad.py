import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# CONFIGURACIÓN DE GOOGLE SHEETS
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# 👉 URL de tu archivo de ENCUESTA DE CALIDAD
SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1WAk0Jv42MIyn0iImsAT2YuCsC8-YphKnFxgJYQZKjqU/edit"
)

# Mapeo: nombre amigable en la app  -> nombre real de la hoja
FORM_SHEETS = {
    "Servicios virtuales y mixtos": "servicios virtual y mixto virtual",
    "Servicios escolarizados y licenciaturas ejecutivas 2025": (
        "servicios escolarizados y licenciaturas ejecutivas 2025"
    ),
    "Preparatoria 2025": "Preparatoria 2025",
}

# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------


@st.cache_data(ttl=120, show_spinner=False)
def _cargar_hoja(nombre_hoja: str) -> pd.DataFrame:
    """
    Carga una hoja específica del Google Sheets y devuelve un DataFrame.

    - Hace único cada encabezado (por si hay '¿Por qué?' repetidos).
    - Convierte 'Marca temporal' a datetime si existe.
    """
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    sh = client.open_by_url(SPREADSHEET_URL)
    ws = sh.worksheet(nombre_hoja)

    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()

    raw_headers = values[0]
    rows = values[1:]

    # Hacer únicos los encabezados
    headers = []
    seen = {}
    for h in raw_headers:
        base = h.strip() if h else "Pregunta"
        if base in seen:
            seen[base] += 1
            base = f"{base} ({seen[base]})"
        else:
            seen[base] = 1
        headers.append(base)

    df = pd.DataFrame(rows, columns=headers)
    df = df.replace("", pd.NA).dropna(how="all")

    # Parsear marca temporal si existe
    if "Marca temporal" in df.columns:
        df["Marca temporal"] = pd.to_datetime(
            df["Marca temporal"], errors="coerce", dayfirst=False
        )

    return df


def _detectar_col_servicio(df: pd.DataFrame) -> str:
    """
    Intenta encontrar la columna que representa el servicio/carrera/programa.
    Si no la encuentra, asume la segunda columna.
    """
    texto_cols = [c.lower() for c in df.columns]

    for col in df.columns:
        lc = col.lower()
        if (
            "programa académico" in lc
            or "programa academico" in lc
            or "servicio" in lc
            or "carrera" in lc
            or "licenciatura" in lc
            or "preparatoria" in lc
        ):
            return col

    # Fallback: segunda columna si existe
    if len(df.columns) >= 2:
        return df.columns[1]
    return df.columns[0]


# Mapeo de respuestas tipo Likert a escala 1–5
LIKERT_MAP = {
    "totalmente de acuerdo": 5,
    "muy de acuerdo": 5,
    "de acuerdo": 4,
    "ni de acuerdo ni en desacuerdo": 3,
    "neutral": 3,
    "indiferente": 3,
    "en desacuerdo": 2,
    "muy en desacuerdo": 1,
    "totalmente en desacuerdo": 1,
}


def _texto_a_puntaje(x):
    if pd.isna(x):
        return pd.NA
    t = str(x).strip().lower()
    return LIKERT_MAP.get(t, pd.NA)


def _detectar_preguntas_likert(df: pd.DataFrame, columnas_a_omitir=None):
    """
    Devuelve la lista de columnas que parecen ser preguntas tipo Likert.
    Se basa en que al menos el 60% de sus valores mapean a 1–5.
    """
    if columnas_a_omitir is None:
        columnas_a_omitir = []

    likert_cols = []
    for col in df.columns:
        if col in columnas_a_omitir:
            continue
        serie = df[col].dropna()
        if serie.empty:
            continue

        # Tomamos una muestra pequeña para decidir
        sample = serie.head(80).map(_texto_a_puntaje)
        if sample.notna().mean() >= 0.6:
            likert_cols.append(col)

    return likert_cols


def _agregar_indice_satisfaccion(df: pd.DataFrame, col_servicio: str):
    """
    Detecta columnas Likert, convierte a 1–5 y agrega:
    - 'Índice de satisfacción' por fila (promedio de sus preguntas likert).
    Devuelve (df_modificado, lista_de_columnas_likert).
    """
    skip_cols = ["Marca temporal", col_servicio]
    likert_cols = _detectar_preguntas_likert(df, skip_cols)

    if not likert_cols:
        df["Índice de satisfacción"] = pd.NA
        return df, []

    likert_numeric = df[likert_cols].applymap(_texto_a_puntaje)
    df["Índice de satisfacción"] = likert_numeric.mean(axis=1)

    return df, likert_cols


# --------------------------------------------------
# PÁGINA PRINCIPAL
# --------------------------------------------------


def pagina_encuesta_calidad():
    st.title("Encuesta de calidad")

    # ---------- Selección de formulario ----------
    st.sidebar.header("Filtros – Encuesta de calidad")

    formulario = st.sidebar.selectbox(
        "Selecciona el formulario",
        list(FORM_SHEETS.keys()),
    )

    nombre_hoja = FORM_SHEETS[formulario]

    with st.spinner(f"Cargando datos de: {formulario}…"):
        df = _cargar_hoja(nombre_hoja)

    if df.empty:
        st.warning("La hoja seleccionada no tiene datos.")
        return

    # Detectar columna de servicio y agregar índice de satisfacción
    col_servicio = _detectar_col_servicio(df)
    df, likert_cols = _agregar_indice_satisfaccion(df, col_servicio)

    # ---------- KPIs generales del formulario ----------
    st.subheader(formulario)

    total_respuestas = len(df)

    if "Marca temporal" in df.columns and df["Marca temporal"].notna().any():
        fecha_min = df["Marca temporal"].min()
        fecha_max = df["Marca temporal"].max()
        rango_fechas = f"{fecha_min.date()} – {fecha_max.date()}"
    else:
        rango_fechas = "No disponible"

    if df["Índice de satisfacción"].notna().any():
        indice_global = df["Índice de satisfacción"].mean()
        indice_texto = f"{indice_global:.2f} / 5"
    else:
        indice_texto = "No calculado"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Respuestas totales", total_respuestas)
    with col2:
        st.metric("Rango de fechas", rango_fechas)
    with col3:
        st.metric("Índice global de satisfacción", indice_texto)

    st.markdown("---")

    # ---------- Filtro por servicio / programa ----------
    servicios = (
        df[col_servicio].dropna().astype(str).sort_values().unique().tolist()
    )
    opciones_servicio = ["(Todos)"] + servicios

    servicio_sel = st.sidebar.selectbox(
        f"Filtrar por servicio / programa\n(columna: '{col_servicio}')",
        opciones_servicio,
    )

    if servicio_sel != "(Todos)":
        df_filtrado = df[df[col_servicio].astype(str) == servicio_sel].copy()
    else:
        df_filtrado = df.copy()

    if df_filtrado.empty:
        st.warning("No hay respuestas para el filtro seleccionado.")
        return

    # Recalcular índice global en el filtro
    if df_filtrado["Índice de satisfacción"].notna().any():
        indice_filtro = df_filtrado["Índice de satisfacción"].mean()
        indice_filtro_txt = f"{indice_filtro:.2f} / 5"
    else:
        indice_filtro_txt = "No calculado"

    st.subheader(
        "Resumen del filtro actual"
        + ("" if servicio_sel == "(Todos)" else f" – {servicio_sel}")
    )

    colf1, colf2 = st.columns(2)
    with colf1:
        st.metric("Respuestas en el filtro", len(df_filtrado))
    with colf2:
        st.metric("Índice de satisfacción (filtro)", indice_filtro_txt)

    # ---------- Promedios por pregunta Likert ----------
    if likert_cols:
        st.markdown("### Promedio por pregunta (escala 1–5)")

        likert_numeric_filtro = df_filtrado[likert_cols].applymap(_texto_a_puntaje)
        promedio_preguntas = (
            likert_numeric_filtro.mean(axis=0)
            .reset_index()
            .rename(columns={"index": "Pregunta", 0: "Promedio 1–5"})
        )
        promedio_preguntas = promedio_preguntas.sort_values(
            "Promedio 1–5", ascending=False
        )

        st.dataframe(promedio_preguntas, use_container_width=True)
    else:
        st.info(
            "No se pudieron identificar preguntas tipo Likert para calcular promedios."
        )

    st.markdown("---")

    # ---------- Tabla detalle de respuestas ----------
    st.markdown("### Respuestas de la encuesta (detalle)")

    # Mostrar solo algunas columnas clave primero, si existen
    columnas_prioritarias = []
    for c in ["Marca temporal", col_servicio, "Índice de satisfacción"]:
        if c in df_filtrado.columns:
            columnas_prioritarias.append(c)

    otras_columnas = [c for c in df_filtrado.columns if c not in columnas_prioritarias]

    columnas_orden = columnas_prioritarias + otras_columnas

    st.dataframe(
        df_filtrado[columnas_orden],
        use_container_width=True,
        height=400,
    )

    st.caption(
        "Las respuestas se actualizan automáticamente cada vez que se envía un nuevo formulario "
        "y la app se vuelve a ejecutar."
    )

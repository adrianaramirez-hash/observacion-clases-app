import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# --------------------------------------------------
# CONFIGURACIÓN DE GOOGLE SHEETS
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1WAk0Jv42MIyn0iImsAT2YuCsC8-YphKnFxgJYQZKjqU"
)

# Nombre que usamos en la app -> nombre real de la hoja
FORM_SHEETS = {
    "Servicios virtuales y mixtos": "servicios virtual y mixto virtual",
    "Servicios escolarizados y licenciaturas ejecutivas 2025": (
        "servicios escolarizados y licenciaturas ejecutivas 2025"
    ),
    "Preparatoria 2025": "Preparatoria 2025",
}

# --------------------------------------------------
# DICCIONARIO DE SECCIONES POR RANGOS DE COLUMNAS
# (Usa letras de Excel: A, B, ..., Z, AA, AB, ..., BA, BB, etc.)
# --------------------------------------------------

SECTION_RANGES = {
    # Formulario 1
    "servicios virtual y mixto virtual": [
        ("Director/Coordinador", "C", "G"),
        ("Aprendizaje", "H", "P"),
        ("Materiales en la plataforma", "Q", "U"),
        ("Evaluación del conocimiento", "V", "Y"),
        ("Acceso a soporte académico", "Z", "AD"),
        ("Acceso a soporte administrativo", "AE", "AI"),
        ("Comunicación con compañeros", "AJ", "AQ"),
        ("Recomendación", "AR", "AU"),
        ("Plataforma SEAC", "AV", "AZ"),
        ("Comunicación con la universidad", "BA", "BE"),
    ],
    # Formulario 2
    "servicios escolarizados y licenciaturas ejecutivas 2025": [
        ("Servicios", "I", "V"),
        ("Servicios académicos", "W", "AH"),
        ("Director/Coordinador", "AI", "AM"),
        ("Instalaciones y equipo tecnológico", "AN", "AX"),
        ("Ambiente escolar", "AY", "BE"),
    ],
    # Formulario 3
    "Preparatoria 2025": [
        ("Servicios", "H", "Q"),
        ("Servicios académicos", "R", "AC"),
        ("Directores y Coordinadores", "AD", "BB"),
        ("Instalaciones y equipo tecnológico", "BC", "BN"),
        ("Ambiente escolar", "BO", "BU"),
    ],
}

# Palabras clave para detectar columnas de comentarios
COMMENT_KEYWORDS = [
    "por qué",
    "porque",
    "comentario",
    "comentarios",
    "sugerencia",
    "sugerencias",
    "observación",
    "observaciones",
    "otro",
    "otros",
    "especifique",
    "explique",
]


# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------


def _col_letter_to_index(col_letter: str) -> int:
    """
    Convierte una letra de columna de Excel (A, B, ..., Z, AA, AB, ...)
    a índice basado en 0 (A=0, B=1, ..., Z=25, AA=26, AB=27, ...).
    """
    col_letter = col_letter.strip().upper()
    total = 0
    for char in col_letter:
        if not ("A" <= char <= "Z"):
            continue
        total = total * 26 + (ord(char) - ord("A") + 1)
    return total - 1  # base 0


@st.cache_data(ttl=120, show_spinner=False)
def _cargar_hoja(nombre_hoja: str) -> pd.DataFrame:
    """
    Carga una hoja específica del Google Sheets y devuelve un DataFrame.

    - Hace único cada encabezado (por si hay repetidos).
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
        sample = serie.head(80).map(_texto_a_puntaje)
        if sample.notna().mean() >= 0.6:
            likert_cols.append(col)
    return likert_cols


def _agregar_indice_satisfaccion(df: pd.DataFrame, col_servicio: str):
    """
    Detecta columnas Likert, convierte a 1–5 y agrega:
    - 'Índice de satisfacción' por fila (promedio de sus preguntas likert).
    Devuelve (df_modificado, lista_de_columnas_likert, dataframe_likert_numerico).
    """
    skip_cols = ["Marca temporal", col_servicio]
    likert_cols = _detectar_preguntas_likert(df, skip_cols)

    if not likert_cols:
        df["Índice de satisfacción"] = pd.NA
        return df, [], pd.DataFrame(index=df.index)

    likert_numeric = df[likert_cols].applymap(_texto_a_puntaje)
    df["Índice de satisfacción"] = likert_numeric.mean(axis=1)

    return df, likert_cols, likert_numeric


def _obtener_columnas_seccion_por_rango(df: pd.DataFrame, nombre_hoja: str, likert_cols):
    """
    A partir de SECTION_RANGES y los nombres de columnas reales,
    devuelve un dict: sección -> lista de columnas (solo Likert) para ese formulario.
    """
    secciones = {}
    if nombre_hoja not in SECTION_RANGES:
        return secciones

    columnas = list(df.columns)

    for nombre_seccion, col_ini, col_fin in SECTION_RANGES[nombre_hoja]:
        idx_ini = _col_letter_to_index(col_ini)
        idx_fin = _col_letter_to_index(col_fin)
        if idx_ini < 0 or idx_fin < 0:
            continue
        # asegurar orden
        if idx_ini > idx_fin:
            idx_ini, idx_fin = idx_fin, idx_ini

        cols_rango = []
        for i, col_name in enumerate(columnas):
            if idx_ini <= i <= idx_fin and col_name in likert_cols:
                cols_rango.append(col_name)

        if cols_rango:
            secciones[nombre_seccion] = cols_rango

    return secciones


def _detectar_columnas_comentarios(df: pd.DataFrame):
    """
    Intenta identificar columnas de texto que sean comentarios abiertos.
    Se basa en el nombre de la columna.
    """
    candidatos = []
    for col in df.columns:
        lc = col.lower()
        if any(p in lc for p in COMMENT_KEYWORDS):
            candidatos.append(col)
    return candidatos


def _top_comentarios(df: pd.DataFrame, comment_cols, top_n=10):
    """
    Junta todas las columnas de comentarios, cuenta repeticiones
    y devuelve un DataFrame con los comentarios más frecuentes.
    """
    textos = []

    for col in comment_cols:
        serie = df[col].dropna().astype(str).str.strip()
        serie = serie[serie != ""]
        textos.extend(serie.tolist())

    if not textos:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])

    s = pd.Series(textos)
    vc = s.value_counts().head(top_n).reset_index()
    vc.columns = ["Comentario", "Frecuencia"]
    return vc


# --------------------------------------------------
# PÁGINA PRINCIPAL
# --------------------------------------------------


def pagina_encuesta_calidad():
    st.title("Encuesta de calidad UDL")

    # ---------- Selección de formulario ----------
    st.sidebar.header("Filtros – Encuesta de calidad")

    nombre_formulario = st.sidebar.selectbox(
        "Selecciona el formulario",
        list(FORM_SHEETS.keys()),
    )

    nombre_hoja = FORM_SHEETS[nombre_formulario]

    with st.spinner(f"Cargando datos de: {nombre_formulario}…"):
        df = _cargar_hoja(nombre_hoja)

    if df.empty:
        st.warning("La hoja seleccionada no tiene datos.")
        return

    # Detectar columna de servicio y agregar índice de satisfacción
    col_servicio = _detectar_col_servicio(df)
    df, likert_cols, likert_numeric = _agregar_indice_satisfaccion(df, col_servicio)

    # Secciones (según rangos de columnas y solo preguntas Likert)
    secciones = _obtener_columnas_seccion_por_rango(df, nombre_hoja, likert_cols)

    # Columnas de comentarios
    comment_cols = _detectar_columnas_comentarios(df)

    # ---------- KPIs generales del formulario ----------
    st.subheader(nombre_formulario)

    total_respuestas = len(df)

    # Periodo de aplicación (mes y año más frecuentes)
    if "Marca temporal" in df.columns and df["Marca temporal"].notna().any():
        meses = df["Marca temporal"].dt.month.dropna()
        años = df["Marca temporal"].dt.year.dropna()
        if not meses.empty and not años.empty:
            mes_mode = int(meses.mode()[0])
            año_mode = int(años.mode()[0])
            periodo = f"{mes_mode:02d}-{año_mode}"
        else:
            periodo = "No disponible"
    else:
        periodo = "No disponible"

    if df["Índice de satisfacción"].notna().any():
        indice_global = df["Índice de satisfacción"].mean()
        indice_texto = f"{indice_global:.2f} / 5"
    else:
        indice_texto = "No calculado"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Respuestas totales", total_respuestas)
    with col2:
        st.metric("Periodo de aplicación", periodo)
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
        likert_numeric_filtrado = likert_numeric.loc[df_filtrado.index]
    else:
        df_filtrado = df.copy()
        likert_numeric_filtrado = likert_numeric.copy()

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

    st.markdown("---")

    # --------------------------------------------------
    # PROMEDIO POR SECCIÓN
    # --------------------------------------------------
    st.markdown("### Promedio por sección (escala 1–5)")

    if secciones:
        resumen_secciones = []
        for nombre_sec, cols_sec in secciones.items():
            datos_sec = likert_numeric_filtrado[cols_sec]
            if datos_sec.notna().any().any():
                prom_sec = datos_sec.mean(axis=1).mean()
                resumen_secciones.append(
                    {
                        "Sección": nombre_sec,
                        "Preguntas incluidas": len(cols_sec),
                        "Promedio 1–5": prom_sec,
                    }
                )

        if resumen_secciones:
            df_secciones = pd.DataFrame(resumen_secciones).sort_values(
                "Promedio 1–5", ascending=False
            )
            st.dataframe(df_secciones, use_container_width=True)
        else:
            st.info(
                "No se pudieron calcular promedios por sección (verifica que las columnas del rango sean tipo Likert)."
            )
    else:
        st.info("No hay secciones configuradas para este formulario.")

    # --------------------------------------------------
    # PROMEDIO POR PREGUNTA
    # --------------------------------------------------
    st.markdown("### Promedio por pregunta (escala 1–5)")

    if likert_cols:
        # Opción para filtrar por sección
        opciones_sec = ["(Todas las secciones)"] + list(secciones.keys())
        sec_sel = st.selectbox(
            "Filtrar preguntas por sección", opciones_sec
        )

        if sec_sel == "(Todas las secciones)":
            cols_preg = likert_cols
        else:
            cols_preg = secciones.get(sec_sel, [])

        if cols_preg:
            promedio_preguntas = (
                likert_numeric_filtrado[cols_preg]
                .mean(axis=0)
                .reset_index()
                .rename(columns={"index": "Pregunta", 0: "Promedio 1–5"})
            )
            promedio_preguntas = promedio_preguntas.sort_values(
                "Promedio 1–5", ascending=False
            )

            st.dataframe(promedio_preguntas, use_container_width=True)
        else:
            st.info("La sección seleccionada no tiene preguntas tipo Likert.")
    else:
        st.info(
            "No se pudieron identificar preguntas tipo Likert para calcular promedios."
        )

    st.markdown("---")

    # --------------------------------------------------
    # DETALLE DE SECCIÓN + COMENTARIOS MÁS REPETIDOS
    # --------------------------------------------------
    st.markdown("### Detalle de sección y comentarios más repetidos")

    if secciones:
        sec_detalle = st.selectbox(
            "Elige una sección para ver detalle y comentarios",
            ["(Ninguna)"] + list(secciones.keys()),
        )
    else:
        sec_detalle = "(Ninguna)"

    if sec_detalle != "(Ninguna)":
        cols_sec = secciones.get(sec_detalle, [])
        if not cols_sec:
            st.warning("No se encontraron columnas para esta sección.")
        else:
            st.markdown(f"**Sección seleccionada:** {sec_detalle}")

            # Promedio por pregunta dentro de la sección
            datos_sec = likert_numeric_filtrado[cols_sec]
            prom_por_preg = (
                datos_sec.mean(axis=0)
                .reset_index()
                .rename(columns={"index": "Pregunta", 0: "Promedio 1–5"})
            )
            st.markdown("**Promedio por pregunta de la sección:**")
            st.dataframe(prom_por_preg, use_container_width=True)

            # Comentarios más repetidos para esta sección:
            # tomamos filas donde haya al menos una respuesta en esa sección
            if comment_cols:
                mask_any = datos_sec.notna().any(axis=1)
                df_resp = df_filtrado.loc[mask_any]

                top_com = _top_comentarios(df_resp, comment_cols, top_n=10)

                st.markdown(
                    "**Comentarios más repetidos (en el filtro y asociados a esta sección):**"
                )
                if top_com.empty:
                    st.write("No se encontraron comentarios repetidos.")
                else:
                    st.dataframe(top_com, use_container_width=True)
            else:
                st.info(
                    "No se detectaron columnas de comentarios en este formulario."
                )

    st.markdown("---")

    # ---------- Tabla detalle de respuestas ----------
    st.markdown("### Respuestas de la encuesta (detalle)")

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

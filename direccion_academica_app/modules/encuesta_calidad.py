import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials
import altair as alt
from collections import Counter

# --------------------------------------------------
# CONFIGURACIÓN PARA GOOGLE SHEETS
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _headers_unicos(headers_raw):
    """
    Recibe la fila de encabezados de la hoja y genera nombres únicos
    por si hay duplicados (ej. '¿Por qué?', '¿Por qué?_2', ...).
    """
    resultado = []
    vistos = {}

    for h in headers_raw:
        base = (h or "").strip()
        if base == "":
            base = "columna"

        if base not in vistos:
            vistos[base] = 1
            resultado.append(base)
        else:
            vistos[base] += 1
            resultado.append(f"{base}_{vistos[base]}")

    return resultado


@st.cache_data(ttl=60)
def cargar_encuesta_calidad():
    """
    Carga las hojas de respuestas de la Encuesta de calidad
    (varios formularios en varias hojas) y las combina
    en un solo DataFrame, tolerando encabezados duplicados.
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
            # Usamos get_all_values para controlar nosotros los encabezados
            valores = ws.get_all_values()

            # Si la hoja está vacía o sólo tiene encabezado, la saltamos
            if not valores or len(valores) < 2:
                continue

            encabezados_raw = valores[0]
            filas = valores[1:]

            encabezados = _headers_unicos(encabezados_raw)

            df_tmp = pd.DataFrame(filas, columns=encabezados)
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
# FUNCIONES DE DETECCIÓN Y TRANSFORMACIÓN
# --------------------------------------------------


def detectar_columna(df, keywords):
    """
    Devuelve la primera columna cuyo nombre contenga TODAS las palabras clave.
    keywords: lista de strings en minúsculas.
    """
    for col in df.columns:
        nombre = str(col).lower()
        if all(k in nombre for k in keywords):
            return col
    return None


def inferir_nivel(programa):
    """Intenta inferir nivel educativo a partir del texto del programa."""
    if not isinstance(programa, str):
        return "Otro"
    s = programa.lower()
    if "preparatoria" in s or "bachillerato" in s:
        return "Preparatoria"
    if "licenciatura" in s or "lic. " in s:
        return "Licenciatura"
    if "maestría" in s or "maestria" in s or "mba" in s:
        return "Posgrado"
    if "doctorado" in s or "phd" in s:
        return "Posgrado"
    return "Otro"


def mapear_likert(valor):
    """
    Convierte respuestas tipo Likert a un número 1–5.
    Maneja variantes como:
    - Totalmente de acuerdo
    - De acuerdo
    - Neutral
    - En desacuerdo
    - Totalmente en desacuerdo
    """
    if pd.isna(valor):
        return None
    s = str(valor).strip().lower()

    # orden importa: primero las opciones más específicas
    if "totalmente en desacuerdo" in s:
        return 1
    if "en desacuerdo" in s:
        return 2
    if "neutral" in s or "ni de acuerdo" in s:
        return 3
    if "totalmente de acuerdo" in s:
        return 5
    if "de acuerdo" in s:
        return 4

    return None


def es_columna_likert(serie):
    """Heurística para decidir si una columna es de escala Likert."""
    valores_mapeados = serie.apply(mapear_likert)
    proporción = valores_mapeados.notna().mean()
    # Si al menos el 40% de los valores se mapearon, la consideramos Likert
    return proporción >= 0.4


STOPWORDS_ES = {
    "de",
    "la",
    "el",
    "y",
    "en",
    "que",
    "los",
    "las",
    "un",
    "una",
    "para",
    "con",
    "muy",
    "por",
    "del",
    "se",
    "al",
    "es",
    "son",
    "lo",
    "sus",
    "su",
    "ya",
    "más",
    "mas",
    "o",
    "a",
}


def top_palabras(series, n=15):
    """
    Cuenta palabras en una serie de textos y devuelve las más frecuentes.
    Sirve para fortalezas, áreas de oportunidad y comentarios.
    """
    counter = Counter()
    for texto in series.dropna():
        if not isinstance(texto, str):
            continue
        # separar muy simple por espacios
        for palabra in texto.replace(",", " ").replace(".", " ").split():
            p = palabra.strip().lower()
            if len(p) < 4:
                continue
            if p in STOPWORDS_ES:
                continue
            counter[p] += 1

    mas_comunes = counter.most_common(n)
    if not mas_comunes:
        return pd.DataFrame(columns=["palabra", "frecuencia"])

    return pd.DataFrame(mas_comunes, columns=["palabra", "frecuencia"])


# --------------------------------------------------
# PÁGINA DEL MÓDULO: ENCUESTA DE CALIDAD
# --------------------------------------------------


def pagina_encuesta_calidad():
    """
    Módulo de Encuesta de calidad.
    Carga datos, aplica filtros, muestra KPIs, gráficas y análisis cualitativo.
    """

    st.subheader("Encuesta de calidad")

    # Cargar datos
    try:
        df = cargar_encuesta_calidad()
    except Exception as e:
        st.error("⚠️ Error técnico al cargar la encuesta de calidad:")
        st.code(str(e))
        return

    if df.empty:
        st.warning("No se encontraron respuestas en las hojas configuradas.")
        return

    # --------------------------------------------------
    # Limpieza mínima / columnas clave
    # --------------------------------------------------

    # Fecha
    col_fecha = None
    for posible in ["Marca temporal", "Fecha", "Timestamp"]:
        if posible in df.columns:
            col_fecha = posible
            df[posible] = pd.to_datetime(df[posible], errors="coerce")
            break

    # Programa / servicio
    col_programa = (
        detectar_columna(df, ["programa", "académico"])
        or detectar_columna(df, ["programa", "academico"])
        or detectar_columna(df, ["programa"])
        or detectar_columna(df, ["servicio"])
        or detectar_columna(df, ["carrera"])
    )

    # Nivel educativo inferido
    if col_programa:
        df["Nivel_educativo"] = df[col_programa].apply(inferir_nivel)
        col_nivel = "Nivel_educativo"
    else:
        col_nivel = None

    # Columnas Likert
    likert_cols = []
    for col in df.columns:
        if col in [col_fecha, col_programa, col_nivel, "__origen_hoja__"]:
            continue
        if es_columna_likert(df[col]):
            likert_cols.append(col)

    # Mapeamos a puntajes
    if likert_cols:
        for col in likert_cols:
            df[col + "__score"] = df[col].apply(mapear_likert)
        score_cols = [c + "__score" for c in likert_cols]
        df["Score_promedio"] = df[score_cols].mean(axis=1, skipna=True)
    else:
        score_cols = []
        df["Score_promedio"] = None

    # Columnas de texto para fortalezas, áreas de oportunidad y comentarios
    col_fort = detectar_columna(df, ["fortaleza"]) or detectar_columna(
        df, ["fortalezas"]
    )
    col_area_op = (
        detectar_columna(df, ["área", "oportunidad"])
        or detectar_columna(df, ["area", "oportunidad"])
        or detectar_columna(df, ["oportunidad"])
    )
    col_coment = (
        detectar_columna(df, ["comentario"])
        or detectar_columna(df, ["sugerencia"])
        or detectar_columna(df, ["observación"])
    )

    # --------------------------------------------------
    # SIDEBAR: FILTROS
    # --------------------------------------------------

    st.sidebar.header("Filtros – Encuesta de calidad")

    df_filtrado = df.copy()

    # Filtro por programa
    if col_programa:
        opciones_prog = ["Todos los programas"] + sorted(
            df[col_programa].dropna().unique().tolist()
        )
        prog_sel = st.sidebar.selectbox("Programa / servicio", opciones_prog)
        if prog_sel != "Todos los programas":
            df_filtrado = df_filtrado[df_filtrado[col_programa] == prog_sel]

    # Filtro por nivel educativo
    if col_nivel:
        opciones_nivel = ["Todos los niveles"] + sorted(
            df["Nivel_educativo"].dropna().unique().tolist()
        )
        nivel_sel = st.sidebar.selectbox("Nivel educativo", opciones_nivel)
        if nivel_sel != "Todos los niveles":
            df_filtrado = df_filtrado[df_filtrado["Nivel_educativo"] == nivel_sel]

    # Filtro por formulario / hoja de origen
    if "__origen_hoja__" in df_filtrado.columns:
        opciones_form = ["Todos los formularios"] + sorted(
            df["__origen_hoja__"].dropna().unique().tolist()
        )
        form_sel = st.sidebar.selectbox("Formulario (hoja de origen)", opciones_form)
        if form_sel != "Todos los formularios":
            df_filtrado = df_filtrado[df_filtrado["__origen_hoja__"] == form_sel]

    st.sidebar.markdown("---")
    st.sidebar.write(f"Respuestas en el filtro actual: **{len(df_filtrado)}**")

    if df_filtrado.empty:
        st.warning("No hay respuestas con los filtros seleccionados.")
        return

    # --------------------------------------------------
    # KPIs
    # --------------------------------------------------

    total_respuestas = len(df_filtrado)

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

    with col_kpi1:
        st.metric("Respuestas totales", total_respuestas)

    with col_kpi2:
        if col_fecha:
            fecha_min = df_filtrado[col_fecha].min()
            fecha_max = df_filtrado[col_fecha].max()
            if pd.notna(fecha_min) and pd.notna(fecha_max):
                rango = f"{fecha_min.date()} – {fecha_max.date()}"
            else:
                rango = "N/D"
            st.metric("Rango de fechas", rango)
        else:
            st.metric("Rango de fechas", "Sin columna de fecha")

    with col_kpi3:
        if col_programa:
            n_servicios = df_filtrado[col_programa].nunique()
            st.metric("Programas / servicios", n_servicios)
        else:
            st.metric("Programas / servicios", "No identificado")

    with col_kpi4:
        if df_filtrado["Score_promedio"].notna().any():
            prom = df_filtrado["Score_promedio"].mean()
            # Escala 1–5 => % de satisfacción
            pct = (prom - 1) / 4 * 100
            st.metric("Satisfacción promedio", f"{prom:.2f} / 5 ({pct:.0f} %)")
        else:
            st.metric("Satisfacción promedio", "No calculable")

    st.markdown("---")

    # --------------------------------------------------
    # GRÁFICAS CUANTITATIVAS
    # --------------------------------------------------

    # 1) Satisfacción por programa
    if col_programa and df_filtrado["Score_promedio"].notna().any():
        st.subheader("Índice de satisfacción por programa / servicio")

        df_prog = (
            df_filtrado.dropna(subset=["Score_promedio"])
            .groupby(col_programa)["Score_promedio"]
            .mean()
            .reset_index()
        )

        chart_prog = (
            alt.Chart(df_prog)
            .mark_bar()
            .encode(
                x=alt.X(col_programa + ":N", title="Programa / servicio"),
                y=alt.Y("Score_promedio:Q", title="Satisfacción promedio (1–5)"),
                tooltip=[col_programa, alt.Tooltip("Score_promedio:Q", format=".2f")],
            )
            .properties(height=300)
        )

        st.altair_chart(chart_prog, use_container_width=True)

    # 2) Satisfacción por nivel educativo
    if col_nivel and df_filtrado["Score_promedio"].notna().any():
        st.subheader("Índice de satisfacción por nivel educativo")

        df_nivel = (
            df_filtrado.dropna(subset=["Score_promedio"])
            .groupby("Nivel_educativo")["Score_promedio"]
            .mean()
            .reset_index()
        )

        chart_nivel = (
            alt.Chart(df_nivel)
            .mark_bar()
            .encode(
                x=alt.X("Nivel_educativo:N", title="Nivel educativo"),
                y=alt.Y("Score_promedio:Q", title="Satisfacción promedio (1–5)"),
                tooltip=[
                    "Nivel_educativo",
                    alt.Tooltip("Score_promedio:Q", format=".2f"),
                ],
            )
            .properties(height=250)
        )

        st.altair_chart(chart_nivel, use_container_width=True)

    # 3) Comparativo entre formularios (hojas)
    if "__origen_hoja__" in df_filtrado.columns and df_filtrado[
        "Score_promedio"
    ].notna().any():
        st.subheader("Comparativo de satisfacción entre formularios")

        df_form = (
            df_filtrado.dropna(subset=["Score_promedio"])
            .groupby("__origen_hoja__")["Score_promedio"]
            .mean()
            .reset_index()
        )

        chart_form = (
            alt.Chart(df_form)
            .mark_bar()
            .encode(
                x=alt.X("__origen_hoja__:N", title="Formulario / hoja"),
                y=alt.Y("Score_promedio:Q", title="Satisfacción promedio (1–5)"),
                tooltip=[
                    "__origen_hoja__",
                    alt.Tooltip("Score_promedio:Q", format=".2f"),
                ],
            )
            .properties(height=250)
        )

        st.altair_chart(chart_form, use_container_width=True)

    # 4) Promedio por pregunta (todas las columnas tipo Likert)
    if likert_cols and df_filtrado["Score_promedio"].notna().any():
        st.subheader("Promedio por pregunta (escala 1–5)")

        promedios_preg = []
        for col, col_score in zip(likert_cols, score_cols):
            serie = df_filtrado[col_score]
            if serie.notna().any():
                promedios_preg.append(
                    {"Pregunta": col, "Score_promedio": serie.mean()}
                )

        if promedios_preg:
            df_preg = pd.DataFrame(promedios_preg)

            chart_preg = (
                alt.Chart(df_preg)
                .mark_bar()
                .encode(
                    x=alt.X("Score_promedio:Q", title="Promedio (1–5)"),
                    y=alt.Y("Pregunta:N", sort="-x", title="Pregunta"),
                    tooltip=[
                        "Pregunta",
                        alt.Tooltip("Score_promedio:Q", format=".2f"),
                    ],
                )
                .properties(height=400)
            )

            st.altair_chart(chart_preg, use_container_width=True)

    st.markdown("---")

    # --------------------------------------------------
    # ANÁLISIS CUALITATIVO (FORTALEZAS, ÁREAS, COMENTARIOS)
    # --------------------------------------------------

    st.subheader("Análisis cualitativo (texto abierto)")

    col1, col2, col3 = st.columns(3)

    # Fortalezas
    if col_fort and col_fort in df_filtrado.columns:
        with col1:
            st.markdown("**Top palabras en fortalezas**")
            df_top_fort = top_palabras(df_filtrado[col_fort], n=10)
            if df_top_fort.empty:
                st.write("Sin registros.")
            else:
                st.dataframe(df_top_fort, use_container_width=True, height=230)
    else:
        with col1:
            st.markdown("**Top palabras en fortalezas**")
            st.write("Columna de fortalezas no identificada.")

    # Áreas de oportunidad
    if col_area_op and col_area_op in df_filtrado.columns:
        with col2:
            st.markdown("**Top palabras en áreas de oportunidad**")
            df_top_area = top_palabras(df_filtrado[col_area_op], n=10)
            if df_top_area.empty:
                st.write("Sin registros.")
            else:
                st.dataframe(df_top_area, use_container_width=True, height=230)
    else:
        with col2:
            st.markdown("**Top palabras en áreas de oportunidad**")
            st.write("Columna de áreas de oportunidad no identificada.")

    # Comentarios generales
    if col_coment and col_coment in df_filtrado.columns:
        with col3:
            st.markdown("**Top palabras en comentarios generales**")
            df_top_com = top_palabras(df_filtrado[col_coment], n=10)
            if df_top_com.empty:
                st.write("Sin registros.")
            else:
                st.dataframe(df_top_com, use_container_width=True, height=230)
    else:
        with col3:
            st.markdown("**Top palabras en comentarios generales**")
            st.write("Columna de comentarios no identificada.")

    st.info(
        "Este análisis de palabras funciona como una 'nube de palabras' simplificada. "
        "Si después quieres, podemos cambiarlo por gráficos específicos para fortalezas y "
        "áreas de oportunidad por programa o nivel."
    )

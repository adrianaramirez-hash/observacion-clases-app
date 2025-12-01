# modules/encuesta_calidad.py

import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials
import altair as alt

# --------------------------------------------------
# CONFIGURACIÓN DE GOOGLE SHEETS
# --------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# URL DEL CONCENTRADO DE CALIDAD 2025
SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1WAk0Jv42MIyn0iImsAT2YuCsC8-YphKnFxgJYQZKjqU/edit"
)

# --------------------------------------------------
# UTILIDADES
# --------------------------------------------------


def _excel_col_to_idx(col_letter: str) -> int:
    """
    Convierte una letra de columna de Excel (A, B, ..., AA, AB, etc.)
    a índice 0-based para usar con df.columns.
    """
    col_letter = col_letter.strip().upper()
    value = 0
    for ch in col_letter:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    # De 1-based (Excel) a 0-based (lista de columnas)
    return value - 1


def _detectar_columnas_likert(df: pd.DataFrame) -> list:
    """
    Detecta columnas que parecen ser escala 1–5.

    - Intenta convertir a numérico (con errors='coerce').
    - Debe haber al menos 1 valor válido.
    - Los valores válidos deben estar entre 1 y 5.

    Si alguna columna causa un TypeError u otro problema raro,
    simplemente se ignora.
    """
    likert_cols = []
    for col in df.columns:
        try:
            serie = pd.to_numeric(df[col], errors="coerce")
        except Exception:
            # Si por algún motivo no se puede convertir, saltamos la columna
            continue

        if serie.notna().sum() == 0:
            continue

        vals = serie.dropna()
        # Si TODOS los valores válidos están entre 1 y 5, la marcamos
        if vals.between(1, 5).all():
            likert_cols.append(col)

    return likert_cols


def _promedio_global_likert(df: pd.DataFrame) -> float | None:
    likert_cols = _detectar_columnas_likert(df)
    if not likert_cols:
        return None
    matriz = df[likert_cols].apply(pd.to_numeric, errors="coerce")
    return float(matriz.stack().mean())


def _promedio_seccion(df: pd.DataFrame, columnas: list[str]) -> float | None:
    if not columnas:
        return None
    matriz = df[columnas].apply(pd.to_numeric, errors="coerce")
    if matriz.notna().sum().sum() == 0:
        return None
    return float(matriz.stack().mean())


def _top_respuestas_texto(serie: pd.Series, top_n: int = 10) -> pd.DataFrame:
    serie = serie.astype(str).str.strip()
    serie = serie[serie != ""]
    if serie.empty:
        return pd.DataFrame(columns=["Respuesta", "Frecuencia"])
    conteo = serie.value_counts().head(top_n)
    return (
        conteo.reset_index()
        .rename(columns={"index": "Respuesta", serie.name: "Frecuencia"})
    )


# --------------------------------------------------
# CONFIG DEL FORMULARIO: NOMBRES Y RANGOS DE SECCIONES
# --------------------------------------------------

FORM_CONFIG = {
    "virtual": {
        "sheet_name": "servicios virtual y mixto virtual",
        "display": "Servicios virtuales y mixtos",
        "sections": [
            {"name": "Director / Coordinador", "start": "c", "end": "g"},
            {"name": "Aprendizaje", "start": "h", "end": "p"},
            {
                "name": "Materiales en la plataforma",
                "start": "q",
                "end": "u",
            },
            {
                "name": "Evaluación del conocimiento",
                "start": "v",
                "end": "y",
            },
            {
                "name": "Acceso a soporte académico",
                "start": "z",
                "end": "ad",
            },
            {
                "name": "Acceso a soporte administrativo",
                "start": "ae",
                "end": "ai",
            },
            {
                "name": "Comunicación con compañeros",
                "start": "aj",
                "end": "aq",
            },
            {"name": "Recomendación", "start": "ar", "end": "au"},
            {"name": "Plataforma SEAC", "start": "av", "end": "az"},
            {
                "name": "Comunicación con la universidad",
                "start": "ba",
                "end": "be",
            },
        ],
    },
    "escolarizados": {
        "sheet_name": "servicios escolarizados y licenciaturas ejecutivas 2025",
        "display": "Servicios escolarizados y licenciaturas ejecutivas",
        "sections": [
            {"name": "Servicios", "start": "i", "end": "v"},
            {"name": "Servicios académicos", "start": "w", "end": "ah"},
            {
                "name": "Director / Coordinador",
                "start": "ai",
                "end": "am",
            },
            {
                "name": "Instalaciones y equipo tecnológico",
                "start": "an",
                "end": "ax",
            },
            {"name": "Ambiente escolar", "start": "ay", "end": "be"},
        ],
    },
    "prepa": {
        "sheet_name": "Preparatoria 2025",
        "display": "Preparatoria UDL",
        "sections": [
            {"name": "Servicios", "start": "h", "end": "q"},
            {"name": "Servicios académicos", "start": "r", "end": "ac"},
            {
                "name": "Directores y coordinadores",
                "start": "ad",
                "end": "bb",
            },
            {
                "name": "Instalaciones y equipo tecnológico",
                "start": "bc",
                "end": "bn",
            },
            {"name": "Ambiente escolar", "start": "bo", "end": "bu"},
        ],
    },
}


# --------------------------------------------------
# CARGA DE DATOS
# --------------------------------------------------


@st.cache_data(ttl=300)
def cargar_datos_encuesta():
    # Credenciales desde st.secrets
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    sh = client.open_by_url(SPREADSHEET_URL)

    # Formularios (3 hojas) — usamos get_all_values para permitir encabezados duplicados
    datos_formularios: dict[str, pd.DataFrame] = {}
    for key, cfg in FORM_CONFIG.items():
        ws = sh.worksheet(cfg["sheet_name"])
        values = ws.get_all_values()
        if not values:
            df = pd.DataFrame()
        else:
            header = values[0]
            rows = values[1:]
            df = pd.DataFrame(rows, columns=header)
        datos_formularios[key] = df

    # Hoja de aplicaciones (metadatos)
    ws_apps = sh.worksheet("Aplicaciones")
    df_apps = pd.DataFrame(ws_apps.get_all_records())

    return datos_formularios, df_apps


# --------------------------------------------------
# UI PRINCIPAL
# --------------------------------------------------


def pagina_encuesta_calidad():
    st.title("Encuesta de calidad")

    try:
        datos_formularios, df_apps = cargar_datos_encuesta()
    except Exception as e:
        st.error("No se pudieron cargar los datos de la Encuesta de calidad.")
        st.exception(e)
        return

    # -----------------------------
    # Selección de formulario
    # -----------------------------
    opciones = {
        "virtual": FORM_CONFIG["virtual"]["display"],
        "escolarizados": FORM_CONFIG["escolarizados"]["display"],
        "prepa": FORM_CONFIG["prepa"]["display"],
    }

    key_form = st.selectbox(
        "Selecciona un formulario",
        options=list(opciones.keys()),
        format_func=lambda k: opciones[k],
    )

    cfg = FORM_CONFIG[key_form]
    df = datos_formularios[key_form]

    if df.empty:
        st.warning("No hay respuestas para este formulario.")
        return

    # -----------------------------
    # Metadatos desde hoja Aplicaciones
    # -----------------------------
    meta = df_apps[df_apps["formulario"] == cfg["sheet_name"]]

    aplicacion_texto = "No definido"
    rango_fechas_texto = "No definido"

    if not meta.empty:
        fila = meta.iloc[0]
        apl_id = str(fila.get("aplicacion_id", "")).strip()
        desc = str(fila.get("descripcion", "")).strip()
        fecha_ini = str(fila.get("fecha_inicio", "")).strip()
        fecha_fin = str(fila.get("fecha_fin", "")).strip()

        if apl_id or desc:
            aplicacion_texto = f"{apl_id} – {desc}".strip(" –")
        if fecha_ini or fecha_fin:
            rango_fechas_texto = f"{fecha_ini} – {fecha_fin}".strip(" –")

    # -----------------------------
    # KPI generales
    # -----------------------------
    respuestas_totales = len(df)
    indice_global = _promedio_global_likert(df)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Respuestas totales", respuestas_totales)

    with col2:
        st.metric("Aplicación", aplicacion_texto)

    with col3:
        st.metric("Rango de fechas", rango_fechas_texto)

    with col4:
        if indice_global is not None:
            st.metric("Índice global de satisfacción", f"{indice_global:.2f} / 5")
        else:
            st.metric("Índice global de satisfacción", "Sin datos")

    st.markdown("---")

    # --------------------------------------------------
    # PROMEDIO POR SECCIÓN
    # --------------------------------------------------
    st.subheader("Promedio por sección (escala 1–5)")

    secciones_cfg = cfg["sections"]
    filas_secciones = []

    # Mapeamos letras de columnas a nombres reales
    for sec in secciones_cfg:
        i_ini = _excel_col_to_idx(sec["start"])
        i_fin = _excel_col_to_idx(sec["end"])
        columnas = list(df.columns[i_ini : i_fin + 1])

        prom = _promedio_seccion(df, columnas)
        filas_secciones.append(
            {
                "Sección": sec["name"],
                "Columnas": f"{sec['start'].upper()}–{sec['end'].upper()}",
                "Promedio 1–5": round(prom, 2) if prom is not None else None,
            }
        )

    df_secciones = pd.DataFrame(filas_secciones)
    st.dataframe(df_secciones[["Sección", "Promedio 1–5"]], use_container_width=True)

    st.markdown("---")

    # --------------------------------------------------
    # PROMEDIO POR PREGUNTA DENTRO DE UNA SECCIÓN
    # --------------------------------------------------
    st.subheader("Promedio por pregunta (escala 1–5)")

    nombres_secciones = [s["name"] for s in secciones_cfg]
    seccion_sel = st.selectbox(
        "Elige una sección para ver sus preguntas",
        options=nombres_secciones,
    )

    cfg_sec = next(s for s in secciones_cfg if s["name"] == seccion_sel)
    idx_ini = _excel_col_to_idx(cfg_sec["start"])
    idx_fin = _excel_col_to_idx(cfg_sec["end"])
    cols_sec = list(df.columns[idx_ini : idx_fin + 1])

    filas_pregs = []
    for col in cols_sec:
        serie = pd.to_numeric(df[col], errors="coerce")
        if serie.notna().sum() == 0:
            filas_pregs.append({"Pregunta": col, "Promedio 1–5": None})
        else:
            vals = serie.dropna()
            if vals.between(1, 5).all():
                filas_pregs.append(
                    {"Pregunta": col, "Promedio 1–5": round(float(vals.mean()), 2)}
                )
            else:
                filas_pregs.append({"Pregunta": col, "Promedio 1–5": None})

    df_pregs = pd.DataFrame(filas_pregs)
    st.dataframe(df_pregs, use_container_width=True)

    st.markdown("---")

    # --------------------------------------------------
    # DETALLE DE UNA PREGUNTA
    # --------------------------------------------------
    st.subheader("Detalle de una pregunta")

    if not cols_sec:
        st.info("La sección seleccionada no tiene columnas asociadas.")
        return

    preg_sel = st.selectbox(
        "Selecciona una pregunta de la sección",
        options=cols_sec,
    )

    serie_bruta = df[preg_sel]

    col_izq, col_der = st.columns(2)

    # Intentamos tratarla como numérica 1–5
    serie_num = pd.to_numeric(serie_bruta, errors="coerce")
    if serie_num.notna().sum() > 0 and serie_num.dropna().between(1, 5).all():
        with col_izq:
            st.write(f"**Promedio (1–5):** {serie_num.mean():.2f}")
            st.write(f"**Respuestas válidas:** {serie_num.notna().sum()}")

        dist = (
            serie_num.value_counts()
            .sort_index()
            .reset_index()
            .rename(columns={"index": "Valor", preg_sel: "Frecuencia"})
        )

        chart = (
            alt.Chart(dist)
            .mark_bar()
            .encode(
                x=alt.X("Valor:O", title="Respuesta (1–5)"),
                y=alt.Y("Frecuencia:Q"),
                tooltip=["Valor", "Frecuencia"],
            )
            .properties(height=250)
        )

        with col_der:
            st.altair_chart(chart, use_container_width=True)

    else:
        st.info("Esta pregunta no es numérica 1–5; se muestran respuestas más frecuentes.")
        top_txt = _top_respuestas_texto(serie_bruta, top_n=10)
        if top_txt.empty:
            st.write("Sin comentarios registrados.")
        else:
            st.write("Respuestas más frecuentes:")
            st.dataframe(top_txt, use_container_width=True)

    if serie_bruta.dtype == "object":
        st.markdown("### Comentarios (muestra)")
        ejemplos = (
            serie_bruta.astype(str).str.strip().replace("", pd.NA).dropna().head(50)
        )
        if ejemplos.empty:
            st.write("Sin comentarios para esta pregunta.")
        else:
            for i, txt in enumerate(ejemplos, start=1):
                st.write(f"{i}. {txt}")

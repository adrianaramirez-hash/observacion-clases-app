import json
from collections import Counter, OrderedDict

import numpy as np
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# -------------------------------------------------------------------
# CONFIGURACIÓN BÁSICA
# -------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# URL del archivo CONCENTRADO_CALIDAD_2025 (el que tiene las 3 hojas + Aplicaciones)
SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1WAk0Jv42MIyn0iImsAT2YuCsC8-YphKnFxgJYQZKjqU"
)

# Helper: convertir letras de columna de Excel a índice 0-based
def _col_letras_a_indice(letras: str) -> int:
    letras = letras.strip().upper()
    idx = 0
    for ch in letras:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


# Config por formulario
# OJO: si cambias nombres de hojas en el archivo de Google Sheets, actualiza "sheet"
FORM_CONFIG = {
    "Servicios virtuales y mixtos": {
        "sheet": "servicios virtual y mixto virtual",
        "aplicaciones_formulario": "servicios virtual y mixto virtual",
        # si quieres forzar una columna de servicio, pon aquí el nombre exacto
        "col_servicio": None,
        "col_fecha": None,  # se detecta por nombre si es None
        # secciones (nombre, col_inicio, col_fin) usando letras de Excel
        "secciones": OrderedDict(
            [
                ("Director / Coordinador", ("C", "G")),
                ("Aprendizaje", ("H", "P")),
                ("Materiales en la plataforma", ("Q", "U")),
                ("Evaluación del conocimiento", ("V", "Y")),
                ("Acceso a soporte académico", ("Z", "AD")),
                ("Acceso a soporte administrativo", ("AE", "AI")),
                ("Comunicación con compañeros", ("AJ", "AQ")),
                ("Recomendación", ("AR", "AU")),
                ("Plataforma SEAC", ("AV", "AZ")),
                ("Comunicación con la universidad", ("BA", "BE")),
            ]
        ),
        # columnas de comentarios (si conoces los nombres exactos, puedes listarlos aquí)
        "comentarios_cols": [],
    },
    "Servicios escolarizados y licenciaturas ejecutivas 2025": {
        "sheet": "servicios escolarizados y licenciaturas ejecutivas 2025",
        "aplicaciones_formulario": "servicios escolarizados y licenciaturas ejecutivas 2025",
        "col_servicio": None,
        "col_fecha": None,
        "secciones": OrderedDict(
            [
                ("Servicios administrativos / operativos", ("I", "V")),
                ("Servicios académicos", ("W", "AH")),
                ("Director / Coordinador", ("AI", "AM")),
                ("Instalaciones y equipo tecnológico", ("AN", "AX")),
                ("Ambiente escolar", ("AY", "BE")),
            ]
        ),
        "comentarios_cols": [],
    },
    "Preparatoria 2025": {
        "sheet": "Preparatoria 2025",
        "aplicaciones_formulario": "Preparatoria 2025",
        "col_servicio": None,
        "col_fecha": None,
        "secciones": OrderedDict(
            [
                ("Servicios administrativos / apoyo", ("H", "Q")),
                ("Servicios académicos", ("R", "AC")),
                ("Directores y coordinadores", ("AD", "BB")),
                ("Instalaciones y equipo tecnológico", ("BC", "BN")),
                ("Ambiente escolar", ("BO", "BU")),
            ]
        ),
        "comentarios_cols": [],
    },
}


# -------------------------------------------------------------------
# CARGA DE DATOS
# -------------------------------------------------------------------


@st.cache_data(ttl=300)
def _cargar_datos_calidad():
    """Carga TODAS las hojas de la encuesta de calidad + hoja Aplicaciones."""
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    sh = client.open_by_url(SPREADSHEET_URL)

    datos_formularios = {}
    for nombre_vista, conf in FORM_CONFIG.items():
        ws = sh.worksheet(conf["sheet"])
        df = pd.DataFrame(ws.get_all_records())
        datos_formularios[nombre_vista] = df

    # Hoja de aplicaciones (una fila por formulario / aplicación anual)
    ws_app = sh.worksheet("Aplicaciones")
    df_app = pd.DataFrame(ws_app.get_all_records())

    return datos_formularios, df_app


# -------------------------------------------------------------------
# MAPEO DE RESPUESTAS A ESCALA 1–5
# -------------------------------------------------------------------


def _mapear_a_likert(valor):
    """Convierte respuestas de texto a escala 1–5.

    Devuelve np.nan cuando no puede mapear.
    """
    if pd.isna(valor):
        return np.nan

    s = str(valor).strip()
    if not s:
        return np.nan

    # Intento directo numérico
    try:
        v = float(s.replace(",", "."))
        # si está en 1–5, lo usamos directo
        if 1 <= v <= 5:
            return v
        # si está en 0–10, lo re-escalamos a 1–5
        if 0 <= v <= 10:
            return (v / 10.0) * 4 + 1
    except Exception:
        pass

    s_low = s.lower()

    # Mapas típicos de satisfacción / acuerdo
    # Orden importante: de más específico a más general
    patrones = [
        (["totalmente en desacuerdo", "muy en desacuerdo"], 1),
        (["en desacuerdo"], 2),
        (["ni de acuerdo", "ni satisfecho", "neutral", "indiferente"], 3),
        (["de acuerdo"], 4),
        (["totalmente de acuerdo", "muy de acuerdo"], 5),
        (["muy insatisfecho"], 1),
        (["insatisfecho"], 2),
        (["poco satisfecho"], 3),
        (["satisfecho"], 4),
        (["muy satisfecho"], 5),
        (["muy malo"], 1),
        (["malo"], 2),
        (["regular"], 3),
        (["bueno"], 4),
        (["muy bueno", "excelente"], 5),
        (["nunca"], 1),
        (["casi nunca"], 2),
        (["a veces"], 3),
        (["casi siempre"], 4),
        (["siempre"], 5),
    ]

    for palabras, puntaje in patrones:
        if any(p in s_low for p in palabras):
            return float(puntaje)

    # Sí / No (solo si no hay nada mejor)
    if s_low in ["sí", "si", "yes"]:
        return 5.0
    if s_low in ["no"]:
        return 1.0

    return np.nan


def _serie_likert(columna):
    return columna.apply(_mapear_a_likert)


# -------------------------------------------------------------------
# UTILIDADES DE CONFIG / DETECCIÓN
# -------------------------------------------------------------------


def _detectar_col_fecha(df: pd.DataFrame, conf: dict) -> str | None:
    if conf.get("col_fecha") and conf["col_fecha"] in df.columns:
        return conf["col_fecha"]
    for col in df.columns:
        c = col.lower()
        if "marca temporal" in c or ("fecha" in c and "nacimiento" not in c):
            return col
    return None


def _detectar_col_servicio(df: pd.DataFrame, conf: dict) -> str | None:
    if conf.get("col_servicio") and conf["col_servicio"] in df.columns:
        return conf["col_servicio"]
    for col in df.columns:
        c = col.lower()
        if any(p in c for p in ["programa", "carrera", "servicio", "nivel educativo"]):
            return col
    return None


def _columnas_de_seccion(df: pd.DataFrame, conf: dict, nombre_seccion: str):
    secciones = conf["secciones"]
    if nombre_seccion not in secciones:
        return []
    letra_ini, letra_fin = secciones[nombre_seccion]
    i_ini = _col_letras_a_indice(letra_ini)
    i_fin = _col_letras_a_indice(letra_fin)
    cols = df.columns.tolist()
    # ajuste por si los índices se salen
    i_ini = max(0, min(i_ini, len(cols) - 1))
    i_fin = max(0, min(i_fin, len(cols) - 1))
    if i_fin < i_ini:
        i_ini, i_fin = i_fin, i_ini
    return cols[i_ini : i_fin + 1]


def _todas_columnas_likert(df: pd.DataFrame, conf: dict):
    """Todas las columnas que participan en las secciones."""
    usadas = []
    for nombre in conf["secciones"].keys():
        usadas.extend(_columnas_de_seccion(df, conf, nombre))
    # quitar duplicados manteniendo orden
    vistos = set()
    resultado = []
    for c in usadas:
        if c not in vistos and c in df.columns:
            vistos.add(c)
            resultado.append(c)
    return resultado


def _detectar_columnas_comentarios(df: pd.DataFrame, conf: dict):
    if conf.get("comentarios_cols"):
        return [c for c in conf["comentarios_cols"] if c in df.columns]
    candidatos = []
    for col in df.columns:
        c = col.lower()
        if any(p in c for p in ["comentario", "sugerencia", "por qué", "por que", "motivo", "explique"]):
            candidatos.append(col)
    return candidatos


# -------------------------------------------------------------------
# CÁLCULOS DE ÍNDICES Y TABLAS
# -------------------------------------------------------------------


def _indice_global_likert(df: pd.DataFrame, conf: dict) -> float | None:
    cols = _todas_columnas_likert(df, conf)
    valores = []
    for c in cols:
        serie = _serie_likert(df[c])
        valores.extend(serie.dropna().tolist())
    if not valores:
        return None
    return float(np.mean(valores))


def _tabla_promedio_secciones(df: pd.DataFrame, conf: dict) -> pd.DataFrame:
    registros = []
    for nombre_seccion in conf["secciones"].keys():
        cols = _columnas_de_seccion(df, conf, nombre_seccion)
        valores = []
        for c in cols:
            if c in df.columns:
                serie = _serie_likert(df[c])
                valores.extend(serie.dropna().tolist())
        prom = float(np.mean(valores)) if valores else None
        registros.append(
            {"Sección": nombre_seccion, "Promedio 1–5": round(prom, 2) if prom is not None else None}
        )
    return pd.DataFrame(registros)


def _tabla_promedio_preguntas(df: pd.DataFrame, conf: dict) -> pd.DataFrame:
    filas = []
    for nombre_seccion in conf["secciones"].keys():
        cols = _columnas_de_seccion(df, conf, nombre_seccion)
        for c in cols:
            if c not in df.columns:
                continue
            serie = _serie_likert(df[c])
            valores = serie.dropna().tolist()
            prom = float(np.mean(valores)) if valores else None
            filas.append(
                {
                    "Sección": nombre_seccion,
                    "Pregunta": c,
                    "Promedio 1–5": round(prom, 2) if prom is not None else None,
                }
            )
    if not filas:
        return pd.DataFrame(columns=["Sección", "Pregunta", "Promedio 1–5"])
    return pd.DataFrame(filas)


def _comentarios_mas_frecuentes(df: pd.DataFrame, conf: dict, max_items: int = 15):
    cols = _detectar_columnas_comentarios(df, conf)
    if not cols:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])

    contador = Counter()
    for c in cols:
        serie = df[c].dropna().astype(str)
        for s in serie:
            text = s.strip()
            if not text:
                continue
            low = text.lower()
            # filtramos respuestas poco útiles
            if low in ["si", "sí", "no", "na", "n/a", "ninguno", "ninguna"]:
                continue
            if len(low) < 4:
                continue
            contador[text] += 1

    if not contador:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])

    items = contador.most_common(max_items)
    return pd.DataFrame(items, columns=["Comentario", "Frecuencia"])


def _info_aplicacion(df_app: pd.DataFrame, conf: dict):
    """Devuelve (aplicacion_str, rango_fechas_str) o valores vacíos."""
    formulario_id = conf.get("aplicaciones_formulario")
    if not formulario_id or df_app.empty or "formulario" not in df_app.columns:
        return "", ""
    fila = df_app[df_app["formulario"] == formulario_id]
    if fila.empty:
        return "", ""
    fila = fila.iloc[0]
    aplicacion = str(fila.get("aplicacion_id", ""))
    desc = str(fila.get("descripcion", "")).strip()
    if desc:
        aplicacion_str = f"{aplicacion} – {desc}"
    else:
        aplicacion_str = aplicacion

    fi = fila.get("fecha_inicio", "")
    ff = fila.get("fecha_fin", "")
    if fi and ff:
        rango = f"{fi} – {ff}"
    else:
        rango = ""
    return aplicacion_str, rango


# -------------------------------------------------------------------
# PÁGINA PRINCIPAL
# -------------------------------------------------------------------


def pagina_encuesta_calidad():
    st.header("Encuesta de calidad")

    datos_formularios, df_aplicaciones = _cargar_datos_calidad()

    # Selector de formulario
    nombres_form = list(FORM_CONFIG.keys())
    formulario_sel = st.selectbox("Selecciona un formulario", nombres_form)

    df_form = datos_formularios.get(formulario_sel, pd.DataFrame())
    conf = FORM_CONFIG[formulario_sel]

    if df_form.empty:
        st.warning("No se encontraron datos para este formulario.")
        return

    # Detectar columnas clave
    col_fecha = _detectar_col_fecha(df_form, conf)
    col_servicio = _detectar_col_servicio(df_form, conf)

    df_trabajo = df_form.copy()

    # Filtro por servicio / carrera
    if col_servicio and col_servicio in df_trabajo.columns:
        servicios = (
            df_trabajo[col_servicio]
            .dropna()
            .astype(str)
            .replace("", np.nan)
            .dropna()
            .unique()
            .tolist()
        )
        servicios = sorted(servicios)
        opcion_servicio = st.selectbox(
            "Filtrar por programa / servicio",
            ["(Todos)"] + servicios,
        )
        if opcion_servicio != "(Todos)":
            df_trabajo = df_trabajo[df_trabajo[col_servicio].astype(str) == opcion_servicio]
    else:
        opcion_servicio = "(Todos)"

    # KPIs
    total_resp = len(df_trabajo)

    aplicacion_str, rango_fechas_str = _info_aplicacion(df_aplicaciones, conf)
    indice_global = _indice_global_likert(df_trabajo, conf)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Respuestas totales", total_resp)
    with col2:
        st.metric("Aplicación", aplicacion_str if aplicacion_str else "Sin registro")
    with col3:
        if indice_global is None or np.isnan(indice_global):
            st.metric("Índice global de satisfacción", "Sin datos")
        else:
            st.metric("Índice global de satisfacción", f"{indice_global:.2f} / 5")

    st.markdown("---")

    # Promedio por sección
    st.subheader("Promedio por sección (escala 1–5)")
    tabla_secciones = _tabla_promedio_secciones(df_trabajo, conf)
    st.dataframe(tabla_secciones, use_container_width=True)

    # Promedio por pregunta
    st.subheader("Promedio por pregunta (escala 1–5)")
    tabla_preguntas = _tabla_promedio_preguntas(df_trabajo, conf)
    if not tabla_preguntas.empty:
        st.dataframe(tabla_preguntas, use_container_width=True)
    else:
        st.info("No se pudieron calcular promedios por pregunta (no hay datos mapeables a 1–5).")

    st.markdown("---")

    # Comentarios más frecuentes
    st.subheader("Comentarios más frecuentes (según filtros actuales)")
    df_coment = _comentarios_mas_frecuentes(df_trabajo, conf)
    if df_coment.empty:
        st.info("No se encontraron comentarios abiertos relevantes.")
    else:
        st.dataframe(df_coment, use_container_width=True)

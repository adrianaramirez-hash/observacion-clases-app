import json
from collections import Counter, OrderedDict

import numpy as np
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SPREADSHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1WAk0Jv42MIyn0iImsAT2YuCsC8-YphKnFxgJYQZKjqU"
)


def _col_letras_a_indice(letras: str) -> int:
    """Convierte letras de columna (ej. 'C') a índice 0-based."""
    letras = letras.strip().upper()
    idx = 0
    for ch in letras:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _columnas_por_rango(df: pd.DataFrame, col_ini: str, col_fin: str):
    """Devuelve nombres de columnas entre col_ini y col_fin (inclusive), usando letras estilo Excel."""
    cols = list(df.columns)
    i_ini = max(0, min(_col_letras_a_indice(col_ini), len(cols) - 1))
    i_fin = max(0, min(_col_letras_a_indice(col_fin), len(cols) - 1))
    if i_fin < i_ini:
        i_ini, i_fin = i_fin, i_ini
    return cols[i_ini : i_fin + 1]


# ------------------------------------------------------------
# CONFIG POR FORMULARIO Y SECCIONES
# ------------------------------------------------------------

FORM_CONFIG = {
    "servicios virtual y mixto virtual": {
        "nombre": "Servicios virtuales y mixtos",
        "sheet": "servicios virtual y mixto virtual",
        "secciones": OrderedDict(
            [
                (
                    "Director / Coordinador",
                    {"rango": ("C", "G"), "eje": "Dirección / Coordinación"},
                ),
                (
                    "Aprendizaje",
                    {"rango": ("H", "P"), "eje": "Servicios académicos"},
                ),
                (
                    "Materiales en la plataforma",
                    {"rango": ("Q", "U"), "eje": "Servicios académicos"},
                ),
                (
                    "Evaluación del conocimiento",
                    {"rango": ("V", "Y"), "eje": "Servicios académicos"},
                ),
                (
                    "Acceso a soporte académico",
                    {"rango": ("Z", "AD"), "eje": "Servicios académicos"},
                ),
                (
                    "Acceso a soporte administrativo",
                    {"rango": ("AE", "AI"), "eje": "Servicios administrativos"},
                ),
                (
                    "Comunicación con compañeros",
                    {"rango": ("AJ", "AQ"), "eje": "Ambiente escolar"},
                ),
                (
                    "Recomendación",
                    {"rango": ("AR", "AU"), "eje": "Satisfacción general"},
                ),
                (
                    "Plataforma SEAC",
                    {"rango": ("AV", "AZ"), "eje": "Servicios académicos"},
                ),
                (
                    "Comunicación con la universidad",
                    {"rango": ("BA", "BE"), "eje": "Comunicación institucional"},
                ),
            ]
        ),
    },
    "servicios escolarizados y licenciaturas ejecutivas 2025": {
        "nombre": "Servicios escolarizados y licenciaturas ejecutivas 2025",
        "sheet": "servicios escolarizados y licenciaturas ejecutivas 2025",
        "secciones": OrderedDict(
            [
                (
                    "Servicios administrativos / apoyo",
                    {"rango": ("I", "V"), "eje": "Servicios administrativos"},
                ),
                (
                    "Servicios académicos",
                    {"rango": ("W", "AH"), "eje": "Servicios académicos"},
                ),
                (
                    "Director / Coordinador",
                    {"rango": ("AI", "AM"), "eje": "Dirección / Coordinación"},
                ),
                (
                    "Instalaciones y equipo tecnológico",
                    {"rango": ("AN", "AX"), "eje": "Infraestructura y equipo"},
                ),
                (
                    "Ambiente escolar",
                    {"rango": ("AY", "BE"), "eje": "Ambiente escolar"},
                ),
            ]
        ),
    },
    "Preparatoria 2025": {
        "nombre": "Preparatoria 2025",
        "sheet": "Preparatoria 2025",
        "secciones": OrderedDict(
            [
                (
                    "Servicios administrativos / apoyo",
                    {"rango": ("H", "Q"), "eje": "Servicios administrativos"},
                ),
                (
                    "Servicios académicos",
                    {"rango": ("R", "AC"), "eje": "Servicios académicos"},
                ),
                (
                    "Directores y coordinadores",
                    {"rango": ("AD", "BB"), "eje": "Dirección / Coordinación"},
                ),
                (
                    "Instalaciones y equipo tecnológico",
                    {"rango": ("BC", "BN"), "eje": "Infraestructura y equipo"},
                ),
                (
                    "Ambiente escolar",
                    {"rango": ("BO", "BU"), "eje": "Ambiente escolar"},
                ),
            ]
        ),
    },
}


# ============================================================
# CARGA DE HOJAS (evitando duplicados en encabezados)
# ============================================================

def _load_ws_as_df(ws) -> pd.DataFrame:
    """Lee una hoja de cálculo en un DataFrame y arregla encabezados duplicados."""
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()

    header = values[0]
    rows = values[1:]

    seen = {}
    fixed_header = []
    for h in header:
        name = h if h else "Columna"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        fixed_header.append(name)

    df = pd.DataFrame(rows, columns=fixed_header)
    df.replace("", np.nan, inplace=True)
    return df


@st.cache_data(ttl=300)
def cargar_datos():
    """Carga los 3 formularios y la hoja Aplicaciones."""
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_url(SPREADSHEET_URL)

    formularios = {}
    for form_id, conf in FORM_CONFIG.items():
        ws = sh.worksheet(conf["sheet"])
        formularios[form_id] = _load_ws_as_df(ws)

    ws_app = sh.worksheet("Aplicaciones")
    df_app = _load_ws_as_df(ws_app)

    # Parseo de fechas en Aplicaciones
    if "fecha_inicio" in df_app.columns:
        df_app["fecha_inicio"] = pd.to_datetime(df_app["fecha_inicio"], errors="coerce")
    if "fecha_fin" in df_app.columns:
        df_app["fecha_fin"] = pd.to_datetime(df_app["fecha_fin"], errors="coerce")

    return formularios, df_app


# ============================================================
# MAPEOS A ESCALA 1–5
# ============================================================

def mapear_a_likert(valor):
    """Convierte texto / número a escala 1–5."""
    if pd.isna(valor):
        return np.nan
    s = str(valor).strip()
    if not s:
        return np.nan

    # Intento numérico directo
    try:
        v = float(s.replace(",", "."))
        if 1 <= v <= 5:
            return v
        if 0 <= v <= 10:
            return (v / 10.0) * 4 + 1  # mapeo 0-10 a 1-5
    except Exception:
        pass

    s_low = s.lower()

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

    if s_low in ["sí", "si", "yes"]:
        return 5.0
    if s_low == "no":
        return 1.0

    return np.nan


def serie_likert(series: pd.Series) -> pd.Series:
    return series.apply(mapear_a_likert)


# ============================================================
# HELPERS: FECHAS / SERVICIOS / COMENTARIOS
# ============================================================

def detectar_col_fecha(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        c = col.lower()
        if "marca temporal" in c or ("fecha" in c and "nac" not in c):
            return col
    return None


def detectar_col_servicio(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        c = col.lower()
        if any(p in c for p in ["programa", "carrera", "servicio", "grupo", "nivel educativo"]):
            return col
    return None


def filtrar_por_aplicacion(df: pd.DataFrame, df_app: pd.DataFrame, formulario_id: str, aplicacion_id: str) -> pd.DataFrame:
    """Filtra un formulario según la aplicación elegida (rango de fechas)."""
    df = df.copy()
    mask_app = (df_app["formulario"] == formulario_id) & (df_app["aplicacion_id"] == aplicacion_id)
    if not mask_app.any():
        return df

    fila = df_app[mask_app].iloc[0]
    f_ini = fila.get("fecha_inicio")
    f_fin = fila.get("fecha_fin")

    col_fecha = detectar_col_fecha(df)
    if col_fecha and pd.notna(f_ini) and pd.notna(f_fin):
        fechas = pd.to_datetime(df[col_fecha], errors="coerce")
        df = df[(fechas >= f_ini) & (fechas <= f_fin)]

    return df


def comentarios_frecuentes(df: pd.DataFrame, max_items: int = 15) -> pd.DataFrame:
    """Encuentra comentarios abiertos más frecuentes."""
    candidatos = []
    for col in df.columns:
        c = col.lower()
        if any(p in c for p in ["comentario", "sugerencia", "por qué", "por que", "opinion", "opinión"]):
            candidatos.append(col)

    if not candidatos:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])

    contador = Counter()
    for c in candidatos:
        serie = df[c].dropna().astype(str)
        for s in serie:
            txt = s.strip()
            if not txt:
                continue
            low = txt.lower()
            if low in ["si", "sí", "no", "na", "n/a", "ninguno", "ninguna"]:
                continue
            if len(low) < 4:
                continue
            contador[txt] += 1

    if not contador:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])

    items = contador.most_common(max_items)
    return pd.DataFrame(items, columns=["Comentario", "Frecuencia"])


# ============================================================
# CÁLCULOS DE PROMEDIOS
# ============================================================

def promedio_seccion(df: pd.DataFrame, col_ini: str, col_fin: str) -> float | None:
    cols = _columnas_por_rango(df, col_ini, col_fin)
    valores = []
    for c in cols:
        serie = serie_likert(df[c])
        valores.extend(serie.dropna().tolist())
    if not valores:
        return None
    return float(np.mean(valores))


def promedios_por_seccion(df: pd.DataFrame, form_id: str) -> pd.DataFrame:
    conf = FORM_CONFIG[form_id]
    registros = []
    for nombre_secc, info in conf["secciones"].items():
        col_ini, col_fin = info["rango"]
        prom = promedio_seccion(df, col_ini, col_fin)
        registros.append(
            {
                "Sección": nombre_secc,
                "Promedio 1–5": round(prom, 2) if prom is not None else None,
            }
        )
    return pd.DataFrame(registros)


def indice_global_formulario(df: pd.DataFrame, form_id: str) -> float | None:
    conf = FORM_CONFIG[form_id]
    valores = []
    for _, info in conf["secciones"].items():
        col_ini, col_fin = info["rango"]
        cols = _columnas_por_rango(df, col_ini, col_fin)
        for c in cols:
            serie = serie_likert(df[c])
            valores.extend(serie.dropna().tolist())
    if not valores:
        return None
    return float(np.mean(valores))


def promedios_por_servicio(df: pd.DataFrame, form_id: str) -> pd.DataFrame:
    col_serv = detectar_col_servicio(df)
    if not col_serv or col_serv not in df.columns:
        return pd.DataFrame()

    conf = FORM_CONFIG[form_id]
    registros = []

    for servicio, df_sub in df.groupby(col_serv):
        valores = []
        for _, info in conf["secciones"].items():
            col_ini, col_fin = info["rango"]
            cols = _columnas_por_rango(df_sub, col_ini, col_fin)
            for c in cols:
                serie = serie_likert(df_sub[c])
                valores.extend(serie.dropna().tolist())
        prom = float(np.mean(valores)) if valores else None
        registros.append(
            {
                "Servicio / programa": servicio,
                "Respuestas": len(df_sub),
                "Promedio global 

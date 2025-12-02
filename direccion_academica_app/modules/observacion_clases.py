import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ------------------------------------------------------------
# Configuración de secciones por formulario
# ------------------------------------------------------------

FORMS_CONFIG = {
    "virtual": {
        "nombre_mostrado": "Servicios virtuales y mixtos",
        "sheet_name": "servicios virtual y mixto virtual",
        # Se intentará detectar automáticamente si cambia el nombre
        "timestamp_col_candidates": ["Marca temporal", "Timestamp", "Fecha y hora"],
        # Se intentará detectar automáticamente la columna carrera/servicio
        "service_col_candidates": ["Programa", "Carrera", "Servicio", "Servicio / programa"],
        "sections": [
            {"name": "Director / Coordinador", "range": "C:G", "eje": "Dirección / Coordinación", "is_direction": True},
            {"name": "Aprendizaje", "range": "H:P", "eje": "Servicios académicos"},
            {"name": "Materiales en la plataforma", "range": "Q:U", "eje": "Servicios académicos"},
            {"name": "Evaluación del conocimiento", "range": "V:Y", "eje": "Servicios académicos"},
            {"name": "Acceso a soporte académico", "range": "Z:AD", "eje": "Servicios académicos"},
            {"name": "Acceso a soporte administrativo", "range": "AE:AI", "eje": "Servicios administrativos / apoyo"},
            {"name": "Comunicación con compañeros", "range": "AJ:AQ", "eje": "Ambiente escolar"},
            {"name": "Recomendación", "range": "AR:AU", "eje": "Satisfacción general"},
            {"name": "Plataforma SEAC", "range": "AV:AZ", "eje": "Infraestructura y equipo"},
            {"name": "Comunicación con la universidad", "range": "BA:BE", "eje": "Comunicación institucional"},
        ],
    },
    "escolar": {
        "nombre_mostrado": "Servicios escolarizados y licenciaturas ejecutivas",
        "sheet_name": "servicios escolarizados y licenciaturas ejecutivas 2025",
        "timestamp_col_candidates": ["Marca temporal", "Timestamp", "Fecha y hora"],
        "service_col_candidates": ["Programa", "Carrera", "Servicio", "Servicio / programa"],
        "sections": [
            {"name": "Servicios administrativos / apoyo", "range": "I:V", "eje": "Servicios administrativos / apoyo"},
            {"name": "Servicios académicos", "range": "W:AH", "eje": "Servicios académicos"},
            {"name": "Director / Coordinador", "range": "AI:AM", "eje": "Dirección / Coordinación", "is_direction": True},
            {"name": "Instalaciones y equipo tecnológico", "range": "AN:AX", "eje": "Infraestructura y equipo"},
            {"name": "Ambiente escolar", "range": "AY:BE", "eje": "Ambiente escolar"},
        ],
    },
    "prepa": {
        "nombre_mostrado": "Preparatoria 2025",
        "sheet_name": "Preparatoria 2025",
        "timestamp_col_candidates": ["Marca temporal", "Timestamp", "Fecha y hora"],
        "service_col_candidates": ["Grupo", "Programa", "Carrera", "Servicio", "Servicio / programa"],
        "sections": [
            {"name": "Servicios administrativos / apoyo", "range": "H:Q", "eje": "Servicios administrativos / apoyo"},
            {"name": "Servicios académicos", "range": "R:AC", "eje": "Servicios académicos"},
            {"name": "Directores y coordinadores", "range": "AD:BB", "eje": "Dirección / Coordinación", "is_direction": True},
            {"name": "Instalaciones y equipo tecnológico", "range": "BC:BN", "eje": "Infraestructura y equipo"},
            {"name": "Ambiente escolar", "range": "BO:BU", "eje": "Ambiente escolar"},
        ],
    },
}

EJES_ORDEN = [
    "Dirección / Coordinación",
    "Servicios académicos",
    "Servicios administrativos / apoyo",
    "Infraestructura y equipo",
    "Ambiente escolar",
    "Comunicación institucional",
    "Satisfacción general",
]

# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def excel_col_to_index(col_letters: str) -> int:
    """Convierte letras de columna de Excel (A, B, ..., Z, AA, AB, ...) a índice 0-based."""
    col_letters = col_letters.strip().upper()
    n = 0
    for ch in col_letters:
        if not ("A" <= ch <= "Z"):
            continue
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1  # 0-based


def get_columns_by_range(df: pd.DataFrame, col_range: str):
    """Obtiene nombres de columnas de un DataFrame usando rango estilo Excel, ej. 'C:G'."""
    try:
        start, end = [s.strip() for s in col_range.split(":")]
        i_start = excel_col_to_index(start)
        i_end = excel_col_to_index(end)
        cols = list(df.columns[max(0, i_start): i_end + 1])
        return cols
    except Exception:
        return []


def detect_column(df: pd.DataFrame, candidates):
    """Encuentra el primer nombre de columna que coincida (insensible a mayúsculas) con alguna candidata."""
    lower_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        cand_lower = cand.lower()
        for col_lower, col_original in lower_map.items():
            if cand_lower in col_lower:
                return col_original
    return None


def detect_timestamp_column(df: pd.DataFrame, candidates):
    col = detect_column(df, candidates)
    if col:
        return col
    # Si no encuentra, usamos la primera columna
    return df.columns[0]


def detect_service_column(df: pd.DataFrame, candidates):
    col = detect_column(df, candidates)
    if col:
        return col
    # fallback: intentamos alguna que contenga 'carrera', 'programa' o 'servicio'
    extra = ["carrera", "programa", "servicio", "grupo"]
    col = detect_column(df, extra)
    return col


def parse_date_safe(value):
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def filter_by_application(df: pd.DataFrame, ts_col: str, start_date, end_date):
    if df.empty:
        return df
    df = df.copy()
    # Convertimos a datetime
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
    mask = pd.Series(True, index=df.index)
    if start_date is not None:
        mask &= df[ts_col].dt.date >= start_date
    if end_date is not None:
        mask &= df[ts_col].dt.date <= end_date
    return df[mask]


def get_question_columns_for_form(df: pd.DataFrame, form_key: str):
    """Une todas las columnas de todas las secciones definidas en FORMS_CONFIG para ese formulario."""
    cfg = FORMS_CONFIG[form_key]
    cols = []
    for sec in cfg["sections"]:
        cols += get_columns_by_range(df, sec["range"])
    # Dejamos solo columnas únicas y que existan
    seen = []
    for c in cols:
        if c not in seen and c in df.columns:
            seen.append(c)
    return seen


def compute_global_index(df: pd.DataFrame, question_cols):
    if df.empty or not question_cols:
        return np.nan
    subset = df[question_cols].apply(pd.to_numeric, errors="coerce")
    return subset.stack().mean()


def compute_section_index(df: pd.DataFrame, cols):
    if df.empty or not cols:
        return np.nan
    subset = df[cols].apply(pd.to_numeric, errors="coerce")
    return subset.stack().mean()


def compute_eje_index_for_all_forms(forms_data):
    """
    forms_data: dict form_key -> (df, question_cols)
    Devuelve dict eje -> promedio global 1–5 considerando todos los formularios.
    """
    eje_values = {eje: [] for eje in EJES_ORDEN}
    for form_key, (df, _) in forms_data.items():
        if df is None or df.empty:
            continue
        cfg = FORMS_CONFIG[form_key]
        for sec in cfg["sections"]:
            eje = sec["eje"]
            cols = get_columns_by_range(df, sec["range"])
            if not cols:
                continue
            subset = df[cols].apply(pd.to_numeric, errors="coerce")
            eje_values[eje].append(subset.values.flatten())
    # Calculamos promedio
    eje_means = {}
    for eje in EJES_ORDEN:
        if not eje_values[eje]:
            eje_means[eje] = np.nan
        else:
            all_vals = np.concatenate(eje_values[eje])
            all_vals = all_vals[~np.isnan(all_vals)]
            eje_means[eje] = all_vals.mean() if len(all_vals) > 0 else np.nan
    return eje_means


def clean_comment(text: str):
    if not isinstance(text, str):
        return ""
    t = text.strip()
    if not t:
        return ""
    # descartamos respuestas típicas de "sin comentario"
    lower = t.lower()
    basura = ["no", "ninguno", "ninguna", "na", "n/a", "no aplica", "sin comentarios", "sin comentario", "ninguno.", "ninguna."]
    if lower in basura:
        return ""
    # descartamos "sí" o similares muy cortos
    if len(t) <= 3 and lower in ["si", "sí", "ok"]:
        return ""
    return t


def extract_top_comments(df: pd.DataFrame):
    if df is None or df.empty:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])
    # Detectamos columnas de texto de comentarios
    cols = [c for c in df.columns if any(k in c.lower() for k in ["coment", "suger", "por qué", "por que", "porque", "observa"])]
    if not cols:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])
    texts = []
    for c in cols:
        texts.extend(df[c].dropna().astype(str).tolist())
    clean_texts = [clean_comment(t) for t in texts]
    clean_texts = [t for t in clean_texts if t]
    if not clean_texts:
        return pd.DataFrame(columns=["Comentario", "Frecuencia"])
    # Agrupamos por texto normalizado
    freq = {}
    example = {}
    for t in clean_texts:
        key = t.strip().lower()
        freq[key] = freq.get(key, 0) + 1
        if key not in example:
            example[key] = t
    rows = [
        {"Comentario": example[k], "Frecuencia": v}
        for k, v in freq.items()
    ]
    df_out = pd.DataFrame(rows).sort_values("Frecuencia", ascending=False)
    return df_out


# ------------------------------------------------------------
# Render de vistas
# ------------------------------------------------------------

def render_vista_rectoria(forms_data, apps_row):
    st.subheader("Panorama institucional (Rectoría)")

    # KPIs globales
    total_respuestas = 0
    for _, (df, _) in forms_data.items():
        if df is not None:
            total_respuestas += len(df)

    # Índice global UDL
    all_vals = []
    for form_key, (df, _) in forms_data.items():
        if df is None or df.empty:
            continue
        question_cols = get_question_columns_for_form(df, form_key)
        subset = df[question_cols].apply(pd.to_numeric, errors="coerce")
        all_vals.append(subset.values.flatten())

    if all_vals:
        concat_vals = np.concatenate(all_vals)
        concat_vals = concat_vals[~np.isnan(concat_vals)]
        indice_udl = concat_vals.mean() if len(concat_vals) > 0 else np.nan
    else:
        indice_udl = np.nan

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Respuestas totales (3 formularios)", f"{total_respuestas}")
    with col2:
        st.metric("Aplicación seleccionada", f"{apps_row['aplicacion_id']} – {apps_row['descripcion']}")
    with col3:
        if pd.isna(indice_udl):
            st.metric("Índice global de satisfacción UDL", "—")
        else:
            st.metric("Índice global de satisfacción UDL", f"{indice_udl:.2f} / 5")

    st.markdown("### Resultados por formulario")
    filas = []
    for form_key, (df, _) in forms_data.items():
        cfg = FORMS_CONFIG[form_key]
        n = 0 if df is None else len(df)
        if df is None or df.empty:
            indice = np.nan
        else:
            question_cols = get_question_columns_for_form(df, form_key)
            indice = compute_global_index(df, question_cols)
        filas.append({
            "Formulario": cfg["nombre_mostrado"],
            "Respuestas": n,
            "Índice global 1–5": round(indice, 2) if not pd.isna(indice) else np.nan,
        })
    st.dataframe(pd.DataFrame(filas))

    st.markdown("### Resultados por eje transversal (todos los formularios)")
    eje_means = compute_eje_index_for_all_forms(forms_data)
    filas_ejes = []
    for eje in EJES_ORDEN:
        filas_ejes.append({
            "Eje transversal": eje,
            "Promedio 1–5": round(eje_means.get(eje, np.nan), 2) if not pd.isna(eje_means.get(eje, np.nan)) else np.nan,
        })
    st.dataframe(pd.DataFrame(filas_ejes))


def render_vista_direccion_academica(forms_data):
    st.subheader("Análisis por formulario (Dirección Académica)")

    # Selector de formulario
    opciones = {FORMS_CONFIG[k]["nombre_mostrado"]: k for k in FORMS_CONFIG.keys()}
    nombre_form = st.selectbox("Formulario", list(opciones.keys()))
    form_key = opciones[nombre_form]
    df, _ = forms_data.get(form_key, (None, None))

    if df is None or df.empty:
        st.info("No hay respuestas para este formulario en la aplicación seleccionada.")
        return

    question_cols = get_question_columns_for_form(df, form_key)
    indice_global = compute_global_index(df, question_cols)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Respuestas del formulario", f"{len(df)}")
    with col2:
        st.metric("Índice global 1–5 del formulario", f"{indice_global:.2f}" if not pd.isna(indice_global) else "—")

    st.markdown("### Promedio por sección")
    cfg = FORMS_CONFIG[form_key]
    filas = []
    for sec in cfg["sections"]:
        cols = get_columns_by_range(df, sec["range"])
        indice = compute_section_index(df, cols)
        filas.append({
            "Sección": sec["name"],
            "Promedio 1–5": round(indice, 2) if not pd.isna(indice) else np.nan,
        })
    st.dataframe(pd.DataFrame(filas))

    st.markdown("### Ranking por servicio / programa")
    service_col = detect_service_column(df, cfg["service_col_candidates"])
    if not service_col:
        st.warning("No se encontró una columna de servicio/carrera/programa para este formulario.")
        return

    df_service = df.copy()
    df_service = df_service[~df_service[service_col].isna()]
    if df_service.empty:
        st.info("No hay servicios con información disponible.")
        return

    # Promedio global por servicio
    rows_rank = []
    for servicio, group in df_service.groupby(service_col):
        indice_serv = compute_global_index(group, question_cols)
        rows_rank.append({
            "Servicio / programa": servicio,
            "Respuestas": len(group),
            "Promedio global 1–5": round(indice_serv, 2) if not pd.isna(indice_serv) else np.nan,
        })
    df_rank = pd.DataFrame(rows_rank).sort_values("Promedio global 1–5", ascending=False)
    st.dataframe(df_rank)


def render_vista_director(forms_data):
    st.subheader("Reporte por servicio (Director / Coordinador)")

    # Selector de formulario
    opciones = {FORMS_CONFIG[k]["nombre_mostrado"]: k for k in FORMS_CONFIG.keys()}
    nombre_form = st.selectbox("Formulario", list(opciones.keys()))
    form_key = opciones[nombre_form]
    df, _ = forms_data.get(form_key, (None, None))

    if df is None or df.empty:
        st.info("No hay respuestas para este formulario en la aplicación seleccionada.")
        return

    cfg = FORMS_CONFIG[form_key]
    service_col = detect_service_column(df, cfg["service_col_candidates"])
    if not service_col:
        st.warning("No se encontró una columna de servicio/carrera/programa para este formulario.")
        return

    servicios_disponibles = sorted(df[service_col].dropna().unique().tolist())
    if not servicios_disponibles:
        st.info("No hay servicios disponibles para seleccionar.")
        return

    servicio_sel = st.selectbox("Servicio / programa", servicios_disponibles)

    df_serv = df[df[service_col] == servicio_sel]
    if df_serv.empty:
        st.info("No hay respuestas para este servicio.")
        return

    question_cols = get_question_columns_for_form(df_serv, form_key)
    indice_global = compute_global_index(df_serv, question_cols)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Servicio / programa", str(servicio_sel))
    with col2:
        st.metric("Respuestas del servicio", f"{len(df_serv)}")
    with col3:
        st.metric("Índice global 1–5 del servicio", f"{indice_global:.2f}" if not pd.isna(indice_global) else "—")

    st.markdown("### Promedios por sección del servicio")
    filas = []
    for sec in cfg["sections"]:
        cols = get_columns_by_range(df_serv, sec["range"])
        indice = compute_section_index(df_serv, cols)
        filas.append({
            "Sección": sec["name"],
            "Promedio 1–5": round(indice, 2) if not pd.isna(indice) else np.nan,
        })
    st.dataframe(pd.DataFrame(filas))

    # Sección especial: detalle de Dirección / Coordinación
    st.markdown("### Detalle de la sección de Dirección / Coordinación")
    direction_sections = [s for s in cfg["sections"] if s.get("is_direction")]
    if not direction_sections:
        st.info("No se identificó una sección de Dirección / Coordinación para este formulario.")
    else:
        sec_dir = direction_sections[0]
        cols_dir = get_columns_by_range(df_serv, sec_dir["range"])
        detalle = []
        for col in cols_dir:
            vals = pd.to_numeric(df_serv[col], errors="coerce")
            detalle.append({
                "Pregunta": col,
                "Promedio 1–5": round(vals.mean(), 2) if not vals.dropna().empty else np.nan,
            })
        st.dataframe(pd.DataFrame(detalle))

    st.markdown("### Comentarios más frecuentes (limpios)")
    df_comentarios = extract_top_comments(df_serv)
    if df_comentarios.empty:
        st.info("No se encontraron comentarios relevantes para este servicio.")
    else:
        st.dataframe(df_comentarios)


# ------------------------------------------------------------
# App principal
# ------------------------------------------------------------

def main():
    st.set_page_config(page_title="Encuesta de calidad UDL", layout="wide")
    st.title("Encuesta de calidad de servicios UDL")

    st.markdown("Sube el archivo de respuestas (exportado de Google Sheets a Excel) que contenga las hojas de los 3 formularios y la hoja **Aplicaciones**.")

    archivo = st.file_uploader("Archivo Excel", type=["xlsx", "xls"])
    if not archivo:
        st.stop()

    try:
        sheets = pd.read_excel(archivo, sheet_name=None)
    except Exception as e:
        st.error(f"No se pudo leer el archivo. Revisa que sea un Excel válido. Detalle: {e}")
        st.stop()

    if "Aplicaciones" not in sheets:
        st.error("No se encontró la hoja 'Aplicaciones'. Verifica el nombre de la hoja en tu archivo.")
        st.stop()

    df_apps = sheets["Aplicaciones"].copy()
    # Normalizamos nombres de columnas esperadas
    df_apps.columns = [str(c).strip().lower() for c in df_apps.columns]

    required_cols = ["formulario", "aplicacion_id", "descripcion", "fecha_inicio", "fecha_fin"]
    for rc in required_cols:
        if rc not in df_apps.columns:
            st.error(f"En la hoja 'Aplicaciones' falta la columna '{rc}'.")
            st.stop()

    # Creamos etiqueta para selector
    df_apps["label"] = df_apps["aplicacion_id"].astype(str) + " – " + df_apps["descripcion"].astype(str)

    # Selector de aplicación (único control que realmente "manda")
    st.sidebar.header("Aplicación")
    label_sel = st.sidebar.selectbox("Selecciona la aplicación", df_apps["label"].tolist())
    
    apps_row = df_apps[df_apps["label"] == label_sel].iloc[0]
    fecha_inicio = parse_date_safe(apps_row["fecha_inicio"])
    fecha_fin = parse_date_safe(apps_row["fecha_fin"])

    # Selector de vista (en la parte superior, sin mencionar rangos de fecha ni marca temporal)
    st.sidebar.header("Vista")
    vista = st.sidebar.radio("Selecciona la vista", ["Rectoría", "Dirección Académica", "Director / Coordinador"])

    # Preparamos los datos filtrados para cada formulario
    forms_data = {}  # form_key -> (df_filtrado, question_cols)
    for form_key, cfg in FORMS_CONFIG.items():
        sheet_name = cfg["sheet_name"]
        if sheet_name not in sheets:
            forms_data[form_key] = (None, [])
            continue
        df_form = sheets[sheet_name].copy()
        if df_form.empty:
            forms_data[form_key] = (None, [])
            continue

        # Detectamos columna de marca temporal (no se muestra en pantalla)
        ts_col = detect_timestamp_column(df_form, cfg["timestamp_col_candidates"])
        if ts_col not in df_form.columns:
            # Si por alguna razón falla, dejamos el DataFrame sin filtrar
            df_filtered = df_form
        else:
            df_filtered = filter_by_application(df_form, ts_col, fecha_inicio, fecha_fin)

        question_cols = get_question_columns_for_form(df_filtered, form_key)
        forms_data[form_key] = (df_filtered, question_cols)

    # Render según vista
    if vista == "Rectoría":
        render_vista_rectoria(forms_data, apps_row)
    elif vista == "Dirección Académica":
        render_vista_direccion_academica(forms_data)
    else:
        render_vista_director(forms_data)


if __name__ == "__main__":
    main()

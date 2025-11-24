import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime
from google.oauth2.service_account import Credentials


# --------------------------------------------------
# CONFIGURACIÓN BÁSICA DE LA PÁGINA
# --------------------------------------------------
st.set_page_config(page_title="Observación de clases", layout="wide")
st.title("📋 Observación de clases – Reportes por corte")

# --------------------------------------------------
# CONEXIÓN A GOOGLE SHEETS
# --------------------------------------------------
# En Streamlit Cloud usaremos st.secrets["gcp_service_account_json"]
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

@st.cache_data(ttl=60)
def cargar_datos_desde_sheets():
    # Credenciales desde secrets (Streamlit Cloud)
    # En secrets guardaremos el JSON completo como texto
    creds_dict = json.loads(st.secrets["gcp_service_account_json"])
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)

    # 👉 URL DE TU GOOGLE SHEETS
    SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1CK7nphUH9YS2JqSWRhrgamYoQdgJCsn5tERA-WnwXes/edit?gid=1166549366#gid=1166549366"

    sh = client.open_by_url(SPREADSHEET_URL)

    # Hoja de respuestas
    ws_resp = sh.worksheet("Respuestas de formulario 1")
    datos_resp = ws_resp.get_all_records()
    df_resp = pd.DataFrame(datos_resp)

    # Hoja de cortes
    ws_cortes = sh.worksheet("Cortes")
    datos_cortes = ws_cortes.get_all_records()
    df_cortes = pd.DataFrame(datos_cortes)

    return df_resp, df_cortes


try:
    df_respuestas, df_cortes = cargar_datos_desde_sheets()
except Exception as e:
    st.error("No se pudieron cargar los datos desde Google Sheets.")
    st.exception(e)
    st.stop()

# --------------------------------------------------
# LIMPIEZA BÁSICA DE DATOS
# --------------------------------------------------

# Columna de fecha: usamos 'Fecha' o 'Marca temporal'
col_fecha = "Fecha" if "Fecha" in df_respuestas.columns else "Marca temporal"
df_respuestas[col_fecha] = pd.to_datetime(df_respuestas[col_fecha], errors="coerce")

# Columnas clave
COL_SERVICIO = "Indica el servicio"
COL_DOCENTE = "Nombre del docente"

for col in [COL_SERVICIO, COL_DOCENTE]:
    if col not in df_respuestas.columns:
        st.error(f"No se encontró la columna '{col}' en la hoja de respuestas.")
        st.stop()

# Hoja de cortes: convertir fechas
if not df_cortes.empty:
    df_cortes["Fecha_inicio"] = pd.to_datetime(df_cortes["Fecha_inicio"], errors="coerce")
    df_cortes["Fecha_fin"] = pd.to_datetime(df_cortes["Fecha_fin"], errors="coerce")

# --------------------------------------------------
# FUNCIONES DE PUNTAJE Y CLASIFICACIÓN
# --------------------------------------------------

def respuesta_a_puntos(valor):
    """Convierte una respuesta (Sí / No / Sin evidencias / número) a puntos."""
    if pd.isna(valor):
        return None
    texto = str(valor).strip().lower()
    if texto in ["sí", "si", "x"]:
        return 3
    if "sin evidencia" in texto or "sin evidencias" in texto:
        return 2
    if texto == "no":
        return 1
    try:
        num = float(texto)
        return num
    except ValueError:
        return None

def clasificar_por_puntos(total_puntos):
    if pd.isna(total_puntos):
        return ""
    # 97 puntos o más → Consolidado
    if total_puntos >= 97:
        return "Consolidado"
    # 76 a 96 → En proceso
    elif total_puntos >= 76:
        return "En proceso"
    # Todo lo demás (0 a 75) → No consolidado
    else:
        return "No consolidado"


# Columnas de puntaje: M a AZ (índices 12 a 51, 0-based)
todas_cols = list(df_respuestas.columns)
start_idx = 12   # M
end_idx = 52     # hasta AZ (52 en 1-based, exclusivo)
cols_puntaje = todas_cols[start_idx:end_idx]

# --------------------------------------------------
# SIDEBAR: SELECCIÓN DE CORTE Y SERVICIO
# --------------------------------------------------

st.sidebar.header("Filtros")

opciones_cortes = ["Todos los cortes"]
if not df_cortes.empty:
    opciones_cortes += list(df_cortes["Corte"])

corte_seleccionado = st.sidebar.selectbox("Selecciona un corte", opciones_cortes)

df_filtrado = df_respuestas.copy()

if corte_seleccionado != "Todos los cortes" and not df_cortes.empty:
    fila_corte = df_cortes[df_cortes["Corte"] == corte_seleccionado]
    if fila_corte.empty:
        st.warning("No se encontró la definición de ese corte.")
    else:
        fecha_ini = fila_corte["Fecha_inicio"].iloc[0]
        fecha_fin = fila_corte["Fecha_fin"].iloc[0]
        if pd.notna(fecha_ini) and pd.notna(fecha_fin):
            mask = (df_filtrado[col_fecha] >= fecha_ini) & (df_filtrado[col_fecha] <= fecha_fin)
            df_filtrado = df_filtrado.loc[mask]

servicios_disponibles = ["Todos los servicios"] + sorted(df_filtrado[COL_SERVICIO].dropna().unique().tolist())
servicio_seleccionado = st.sidebar.selectbox("Selecciona un servicio", servicios_disponibles)

if servicio_seleccionado != "Todos los servicios":
    df_filtrado = df_filtrado[df_filtrado[COL_SERVICIO] == servicio_seleccionado]

st.sidebar.markdown("---")
st.sidebar.write(f"Observaciones en el filtro actual: **{len(df_filtrado)}**")

if df_filtrado.empty:
    st.warning("No hay observaciones para el corte/servicio seleccionado.")
    st.stop()

# --------------------------------------------------
# CÁLCULO DE PUNTOS POR OBSERVACIÓN
# --------------------------------------------------

def calcular_total_puntos_fila(row):
    total = 0
    for col in cols_puntaje:
        if col not in row.index:
            continue
        puntos = respuesta_a_puntos(row[col])
        if puntos is not None:
            total += puntos
    return total

df_filtrado = df_filtrado.copy()
df_filtrado["Total_puntos_observación"] = df_filtrado.apply(calcular_total_puntos_fila, axis=1)

# ------------------------------------------------------------------
# TARJETAS RESUMEN (KPIs) Y GRÁFICA DE CLASIFICACIÓN
# ------------------------------------------------------------------

# OJO: este bloque asume que ya existe un DataFrame df_filtrado
# con las observaciones según los filtros de corte y servicio,
# y que tiene al menos estas columnas:
#   - "Clasificación"  (Consolidado / En proceso / No consolidado)
#   - "Indica el servicio"

# Si tu DataFrame filtrado se llama diferente, cámbialo aquí.
df_base = df_filtrado.copy()

total_obs = len(df_base)

if total_obs > 0:
    # Conteos por clasificación
    n_consol = (df_base["Clasificación"] == "Consolidado").sum()
    n_proceso = (df_base["Clasificación"] == "En proceso").sum()
    n_no = (df_base["Clasificación"] == "No consolidado").sum()

    pct_consol = n_consol * 100 / total_obs
    pct_proceso = n_proceso * 100 / total_obs
    pct_no = n_no * 100 / total_obs
else:
    n_consol = n_proceso = n_no = 0
    pct_consol = pct_proceso = pct_no = 0

# Fila de tarjetas
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.metric("Obs. totales", total_obs)

with col_kpi2:
    st.metric("% Consolidado", f"{pct_consol:.0f} %")

with col_kpi3:
    st.metric("% En proceso", f"{pct_proceso:.0f} %")

with col_kpi4:
    st.metric("% No consolidado", f"{pct_no:.0f} %")

st.markdown("---")

# ------------------------------------------------------------------
# GRÁFICA DE CLASIFICACIÓN POR SERVICIO
# ------------------------------------------------------------------
import altair as alt

if total_obs > 0:
    df_graf = (
        df_base
        .groupby(["Indica el servicio", "Clasificación"])
        .size()
        .reset_index(name="conteo")
    )

    # Pasar a porcentaje dentro de cada servicio
    df_totales_servicio = (
        df_graf.groupby("Indica el servicio")["conteo"].transform("sum")
    )
    df_graf["porcentaje"] = df_graf["conteo"] * 100 / df_totales_servicio

    st.subheader("Clasificación por servicio")

    chart = (
        alt.Chart(df_graf)
        .mark_bar()
        .encode(
            x=alt.X("Indica el servicio:N", title="Servicio"),
            y=alt.Y("porcentaje:Q", title="Porcentaje"),
            color=alt.Color("Clasificación:N"),
            tooltip=[
                "Indica el servicio",
                "Clasificación",
                alt.Tooltip("porcentaje:Q", format=".1f", title="Porcentaje (%)"),
                "conteo"
            ]
        )
        .properties(
            height=300
        )
    )

    st.altair_chart(chart, use_container_width=True)

st.markdown("---")

# --------------------------------------------------
# RESUMEN POR SERVICIO
# --------------------------------------------------

st.subheader("Resumen por servicio")

resumen_servicio = (
    df_filtrado
    .groupby(COL_SERVICIO)
    .agg(
        Observaciones=("Total_puntos_observación", "count"),
        Docentes_observados=(COL_DOCENTE, "nunique"),
        Total_puntos=("Total_puntos_observación", "sum")
    )
    .reset_index()
)

resumen_servicio["Promedio_puntos_por_obs"] = resumen_servicio["Total_puntos"] / resumen_servicio["Observaciones"]

st.dataframe(resumen_servicio, use_container_width=True)

# --------------------------------------------------
# DETALLE POR DOCENTE
# --------------------------------------------------

st.subheader("Detalle por docente (en el corte/servicio seleccionado)")

resumen_docente = (
    df_filtrado
    .groupby(COL_DOCENTE)
    .agg(
        N_observaciones=("Total_puntos_observación", "count"),
        Total_puntos=("Total_puntos_observación", "sum")
    )
    .reset_index()
)

resumen_docente["Clasificación"] = resumen_docente["Total_puntos"].apply(clasificar_por_puntos)

st.dataframe(resumen_docente, use_container_width=True)

# --------------------------------------------------
# HISTORIAL DE UN DOCENTE
# --------------------------------------------------

st.subheader("Historial de observaciones de un docente (dentro del filtro)")

docentes_lista = sorted(resumen_docente[COL_DOCENTE].dropna().unique().tolist())
docente_sel = st.selectbox("Selecciona un docente", ["(ninguno)"] + docentes_lista)

if docente_sel != "(ninguno)":
    df_doc = df_filtrado[df_filtrado[COL_DOCENTE] == docente_sel].copy()
    df_doc = df_doc[[col_fecha, COL_SERVICIO, "Total_puntos_observación"]]
    df_doc = df_doc.sort_values(col_fecha)
    df_doc.rename(columns={col_fecha: "Fecha"}, inplace=True)
    df_doc["Clasificación_observación"] = df_doc["Total_puntos_observación"].apply(clasificar_por_puntos)

    st.write(f"Observaciones de **{docente_sel}** en el filtro actual:")
    st.dataframe(df_doc, use_container_width=True)

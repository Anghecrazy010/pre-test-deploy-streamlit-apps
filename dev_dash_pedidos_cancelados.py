import streamlit as st
from sqlalchemy import create_engine
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from urllib.parse import urlencode
import requests
import time
import os
from sqlalchemy.exc import SQLAlchemyError


# --- Configurar página ---
st.set_page_config(
    page_title="Dashboard Pedidos Cancelados",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Leer secretos ---
AUTH0_CLIENT_ID = os.environ["AUTH0_CLIENT_ID"]
AUTH0_CLIENT_SECRET = os.environ["AUTH0_CLIENT_SECRET"]
AUTH0_DOMAIN = os.environ["AUTH0_DOMAIN"]
REDIRECT_URI = "https://pedidos-cancelados-test.netlify.app/"

# --- URLs de Auth0 ---
AUTH0_AUTHORIZE_URL = f"https://{AUTH0_DOMAIN}/authorize"
AUTH0_TOKEN_URL = f"https://{AUTH0_DOMAIN}/oauth/token"
AUTH0_USERINFO_URL = f"https://{AUTH0_DOMAIN}/userinfo"
AUTH0_LOGOUT_URL = f"https://{AUTH0_DOMAIN}/v2/logout"

# --- Función para construir URL de login ---
def build_login_url():
    return AUTH0_AUTHORIZE_URL + "?" + urlencode({
        "response_type": "code",
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email",
    })

# --- Función para obtener el token de acceso ---
def get_token(code):
    data = {
        "grant_type": "authorization_code",
        "client_id": AUTH0_CLIENT_ID,
        "client_secret": AUTH0_CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    response = requests.post(AUTH0_TOKEN_URL, data=data)
    return response.json()

# --- Función para obtener el perfil del usuario ---
def get_user_info(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(AUTH0_USERINFO_URL, headers=headers)
    return response.json()

# --- Autenticación manual ---
code = st.query_params.get("code")

if "user" not in st.session_state and code:
    token_data = get_token(code)
    access_token = token_data.get("access_token")
    if access_token:
        user_info = get_user_info(access_token)
        st.session_state.user = user_info
        st.query_params.clear()  # Limpia parámetros en URL tras login


# --- Si no estás autenticado, muestra login ---
if "user" not in st.session_state:
    
    st.title("Bienvenido al Dashboard de Pedidos Cancelados")
    st.markdown("Para acceder, inicia sesión con el siguiente botón:")
    login_url = build_login_url()
    st.markdown(f"[🔐 Iniciar sesión con Auth0]({login_url})", unsafe_allow_html=True)
    st.stop()

# --- Botón cerrar sesión ---
logout_url = AUTH0_LOGOUT_URL + "?" + urlencode({
    "returnTo": REDIRECT_URI,
    "client_id": AUTH0_CLIENT_ID
})



with st.sidebar:
    
    if "user" in st.session_state:
        st.markdown(f"""
    <div style='display: flex; flex-direction: column; align-items: center;'>
        <img src="{st.session_state.user['picture']}" 
             style="border-radius: 50%; width: 100px; height: 100px; object-fit: cover;"/>
        <p style='margin-top: 10px; font-weight: bold;'>{st.session_state.user['name']}</p>
    </div>
""", unsafe_allow_html=True)
    
    if st.button("Cerrar sesión", use_container_width=True):
        st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{logout_url}\'" />', unsafe_allow_html=True)
    

# --- Mostrar mensaje de bienvenida temporal ---
if "welcome_shown" not in st.session_state:
    welcome_placeholder = st.empty()
    welcome_placeholder.success(f"Bienvenido, {st.session_state.user['name']} 👋")
    time.sleep(5)
    welcome_placeholder.empty()
    st.session_state.welcome_shown = True  # Evita que vuelva a mostrarse

# --- Función para crear el gráfico de dona ---
def donut_plotly(percentage, color_palette):
    if color_palette == 'green':
        chart_colors = ['#27AE60', '#12783D']  # Verde
    elif color_palette == 'red':
        chart_colors = ['#E74C3C', '#781F16']  # Rojo
    else:
        chart_colors = ['#29b5e8', '#155F7A']  #  azul

    fig = go.Figure(data=[go.Pie(
        labels=['CANCELADO', 'FACTURADO'],
        values=[100 - percentage, percentage],  # corregido: porcentaje facturado
        hole=0.6,
        marker_colors=chart_colors,
        textinfo='none'
    )])

    fig.add_annotation(
        text=f"{percentage}%",
        font_size=24,
        showarrow=False
    )

    fig.update_layout(
        showlegend=False,
        width=250,
        height=250,
        margin=dict(t=0, b=0, l=0, r=0)
    )

    return fig
# Crear motor SQLAlchemy a partir de la URL del archivo secrets.toml
engine = create_engine(os.environ["EBS12"])

# Consulta con cacheo
@st.cache_data(ttl=120)  # Cachea por 10 minutos
def obtener_datos():
    query = r"""
    
Select 
	ooha.HEADER_ID,
	RCTA.PURCHASE_ORDER		AS OCC,
	OOHA.ORDER_NUMBER		AS [No PEDIDO ORACLE],
	HAOU.NAME				AS ALMACEN,
	HPSF.PARTY_SITE_NUMBER	AS CLIENTE_FACTURACION,
    HPS.PARTY_SITE_NUMBER	AS CLIENTE_ENTREGA,
    HP.PARTY_NAME			AS CLIENTE,
	HP.Party_ID				AS Party_ID,
	client.Formato			AS FORMATO,
	client.Canal			AS CANAL,
	OOHA.PRICING_DATE		AS [FECHA OC],
	OOHA.ATTRIBUTE6			AS [FECHA ENTREGA],
	OOHA.ATTRIBUTE1			AS [FECHA CANCELACION],
	OOLA.LINE_NUMBER		AS LINEA,
	MSIB.SEGMENT1			AS SKU,
	MSIB.DESCRIPTION		AS DESCRIPCION,
	pro.[Unidad de Negocio]	AS FAMILIA,
	PRO.[Factor Conversion]	AS [Factor Conversion],
	Muc.CONVERSION_RATE		AS [Tarimas a cajas],
	OOLA.ORDER_QUANTITY_UOM	AS UDM,
	ISNULL(Muc.CONVERSION_RATE,	1) * (COALESCE(RCTL.QUANTITY_CREDITED, 0) + COALESCE(RCTL.QUANTITY_INVOICED, 0)) AS [CANTIDAD FACTURADA],
	ISNULL(Muc.CONVERSION_RATE,	1) * (OOLA.ORDERED_QUANTITY)	AS [CANTIDAD ORDENADA],
	ISNULL(Muc.CONVERSION_RATE,	1) * (OOLA.CANCELLED_QUANTITY)	AS	[CANTIDAD CANCELADA],
	--ISNULL(FND.LOOKUP_CODE, FND.LOOKUP_CODE) AS [CODIGO MOTIVO],
	--ISNULL(FND.DESCRIPTION, FND.DESCRIPTION) AS [MOTIVO CANCELACION],
	FND.LOOKUP_CODE AS CODIGO_MOTIVO,
	FND.DESCRIPTION AS MOTIVO_CANCELACION,
 
	TL.NAME					AS [TIPO PEDIDO],
	OOHA.CREATION_DATE		AS [FECHA CREACION],
	RCTA.TRX_NUMBER			AS FACTURA,
	RCTA.TRX_DATE			AS [FECHA FACTURA]
 
 
 
from
RA_CUSTOMER_TRX_ALL RCTA
LEFT JOIN RA_CUST_TRX_TYPES_ALL			RCTTA	ON RCTTA.CUST_TRX_TYPE_ID = RCTA.CUST_TRX_TYPE_ID  
LEFT JOIN RA_CUSTOMER_TRX_LINES_ALL		RCTL	ON RCTL.CUSTOMER_TRX_ID = RCTA.CUSTOMER_TRX_ID 
LEFT JOIN OE_ORDER_LINES_ALL			OOLA	ON OOLA.LINE_ID = RCTL.INTERFACE_LINE_ATTRIBUTE6
LEFT JOIN OE_ORDER_HEADERS_ALL			OOHA	ON OOHA.HEADER_ID = OOLA.HEADER_ID
LEFT JOIN OE_TRANSACTION_TYPES_TL		TL		ON TL.TRANSACTION_TYPE_ID = OOHA.ORDER_TYPE_ID and TL.LANGUAGE = 'ESA'
LEFT JOIN MTL_SYSTEM_ITEMS_B			MSIB	ON MSIB.INVENTORY_ITEM_ID	= RCTL.INVENTORY_ITEM_ID AND MSIB.ORGANIZATION_ID = 101
LEFT JOIN HR_ALL_ORGANIZATION_UNITS		HAOU	ON HAOU.ORGANIZATION_ID = OOLA.SHIP_FROM_ORG_ID
LEFT JOIN HZ_CUST_SITE_USES_ALL			HCSUA	ON HCSUA.SITE_USE_ID = OOHA.SHIP_TO_ORG_ID 
LEFT JOIN HZ_CUST_ACCT_SITES_ALL		HCAS	ON HCAS.CUST_ACCT_SITE_ID = HCSUA.CUST_ACCT_SITE_ID 
LEFT JOIN HZ_PARTY_SITES				HPS		ON HPS.PARTY_SITE_ID = HCAS.PARTY_SITE_ID
left JOIN HZ_PARTIES					HP		ON HP.PARTY_ID = HPS.PARTY_ID 
left JOIN HZ_CUST_SITE_USES_ALL			HCSUAF	ON HCSUAF.SITE_USE_ID = OOHA.INVOICE_TO_ORG_ID 
left JOIN HZ_CUST_ACCT_SITES_ALL		HCASF   ON HCASF.CUST_ACCT_SITE_ID = HCSUAF.CUST_ACCT_SITE_ID 
Left JOIN HZ_PARTY_SITES				HPSF    ON HPSF.PARTY_SITE_ID = HCASF.PARTY_SITE_ID 
left JOIN HZ_PARTIES					HPF		ON HPF.PARTY_ID = HPSF.PARTY_ID 
left JOIN HZ_CUST_ACCOUNTS				HCA		ON HCA.CUST_ACCOUNT_ID = HCAS.CUST_ACCOUNT_ID 
Left Join [PICO_VENTAS].[dbo].[clientes] client On client.[No_] = HPS.PARTY_SITE_NUMBER
left Join [PICO_VENTAS].[dbo].[productos] pro 	ON pro.[No_] = MSIB.SEGMENT1
Left Join MTL_UOM_CONVERSIONS			MUC		On Muc.[UOM_CODE] = RCTL.UOM_CODE and Muc.[INVENTORY_ITEM_ID] = RCTL.[INVENTORY_ITEM_ID]
LEFT JOIN FND_LOOKUP_VALUES				FND		ON FND.LOOKUP_CODE= RCTA.REASON_CODE AND FND.LANGUAGE = 'ESA' AND FND.VIEW_APPLICATION_ID = RCTA.PROGRAM_APPLICATION_ID AND FND.DESCRIPTION IS NOT NULL
 
 
 
where (RCTL.QUANTITY_CREDITED IS NOT NULL OR RCTL.QUANTITY_INVOICED IS NOT NULL)
and CONVERT(DATETIME, CONVERT(DATE, OOHA.CREATION_DATE)) > '01-01-2022'

and RCTA.ORG_ID = 81
AND OOHA.ORG_ID = 81
 
 
UNION
 
 

 
SELECT DISTINCT 
	OOHA.HEADER_ID,
	OOLA.CUST_PO_NUMBER			AS		OCC,
	OOHA.ORDER_NUMBER			AS		[No PEDIDO ORACLE],
	HAOU.NAME					AS		ALMACEN,
	HPSF.PARTY_SITE_NUMBER		AS		CLIENTE_FACTURACION,
    HPS.PARTY_SITE_NUMBER		AS		CLIENTE_ENTREGA,
    HP.PARTY_NAME				AS		CLIENTE,
	HP.Party_ID					AS		Party_ID,
	client.Formato				AS		FORMATO,
	client.Canal				AS		CANAL,
	OOHA.PRICING_DATE			AS		[FECHA OC],
	OOHA.ATTRIBUTE6				AS		[FECHA ENTREGA],
	OOHA.ATTRIBUTE1				AS		[FECHA CANCELACION],
	OOLA.LINE_NUMBER			AS		LINEA,
	MSIB.SEGMENT1				AS		SKU,
	MSIB.DESCRIPTION			AS		DESCRIPCION,
	pro.[Unidad de Negocio]		AS		FAMILIA,
	PRO.[Factor Conversion]		AS		[Factor Conversion],
	Muc.CONVERSION_RATE			AS [Tarimas a cajas],
	OOLA.ORDER_QUANTITY_UOM	AS UDM,
	NULL						AS		[CANTIDAD FACTURADA],
	NULL						AS		[CANTIDAD ORDENADA],
	ISNULL(Muc.CONVERSION_RATE,	1) * (OOLA.CANCELLED_QUANTITY)	AS	[CANTIDAD CANCELADA],
	FND.LOOKUP_CODE				AS		[CODIGO MOTIVO],
	FND.DESCRIPTION				AS		[MOTIVO CANCELACION],
 
 
 
	TL.NAME						AS		[TIPO PEDIDO],
	OOLA.CREATION_DATE			AS		[FECHA_CREACION],
	NULL						AS		FACTURA,
	NULL						AS		[FECHA FACTURA]
 
 

 
 
FROM OE_ORDER_LINES_ALL OOLA
LEFT JOIN OE_ORDER_HEADERS_ALL			OOHA	ON OOHA.HEADER_ID = OOLA.HEADER_ID
LEFT JOIN MTL_SYSTEM_ITEMS_B			MSIB	ON MSIB.INVENTORY_ITEM_ID	= OOLA.INVENTORY_ITEM_ID AND MSIB.ORGANIZATION_ID = 101
left JOIN OE_TRANSACTION_TYPES_TL		TL		ON TL.TRANSACTION_TYPE_ID = OOHA.ORDER_TYPE_ID and TL.LANGUAGE = 'ESA'
LEFT JOIN HR_ALL_ORGANIZATION_UNITS		HAOU	ON HAOU.ORGANIZATION_ID = OOLA.SHIP_FROM_ORG_ID
LEFT JOIN HZ_CUST_SITE_USES_ALL			HCSUA	ON HCSUA.SITE_USE_ID = OOHA.SHIP_TO_ORG_ID 
LEFT JOIN HZ_CUST_ACCT_SITES_ALL		HCAS	ON HCAS.CUST_ACCT_SITE_ID = HCSUA.CUST_ACCT_SITE_ID 
LEFT JOIN HZ_PARTY_SITES				HPS		ON HPS.PARTY_SITE_ID = HCAS.PARTY_SITE_ID
left JOIN HZ_PARTIES					HP		ON HP.PARTY_ID = HPS.PARTY_ID 
left JOIN HZ_CUST_SITE_USES_ALL			HCSUAF	ON HCSUAF.SITE_USE_ID = OOHA.INVOICE_TO_ORG_ID 
left JOIN HZ_CUST_ACCT_SITES_ALL		HCASF   ON HCASF.CUST_ACCT_SITE_ID = HCSUAF.CUST_ACCT_SITE_ID 
Left JOIN HZ_PARTY_SITES				HPSF    ON HPSF.PARTY_SITE_ID = HCASF.PARTY_SITE_ID 
left JOIN HZ_PARTIES					HPF		ON HPF.PARTY_ID = HPSF.PARTY_ID 
left JOIN HZ_CUST_ACCOUNTS				HCA		ON HCA.CUST_ACCOUNT_ID = HCAS.CUST_ACCOUNT_ID 
Left Join [PICO_VENTAS].[dbo].[clientes] client On client.[No_] = HPS.PARTY_SITE_NUMBER
left Join [PICO_VENTAS].[dbo].[productos] pro 	ON pro.[No_] = MSIB.SEGMENT1
Left Join MTL_UOM_CONVERSIONS			MUC		On Muc.[UOM_CODE] = OOLA.ORDER_QUANTITY_UOM and Muc.[INVENTORY_ITEM_ID] = OOLA.[INVENTORY_ITEM_ID]
LEFT JOIN OE_REASONS					REA		On REA.HEADER_ID = OOHA.HEADER_ID AND REA.ENTITY_ID = OOLA.LINE_ID
inner JOIN FND_LOOKUP_VALUES			FND		ON FND.LOOKUP_CODE = REA.REASON_CODE AND FND.LANGUAGE = 'ESA'  AND FND.LOOKUP_TYPE = 'CANCEL_CODE'
 
 
WHERE OOLA.FLOW_STATUS_CODE = 'CANCELLED'
and OOLA.ORG_ID = 81
and CONVERT(DATETIME, CONVERT(DATE, OOHA.CREATION_DATE)) > '01-01-2022'
    
    
    
    """

    try:
        with engine.connect() as connection:
            return pd.read_sql(query, connection)
    except SQLAlchemyError as e:
        # Lanzamos la excepción para que Streamlit pueda manejarla fuera
        raise RuntimeError(f"Error al ejecutar la consulta: {str(e)}")

# Lógica en la app para mostrar el error en la interfaz
try:
    df = obtener_datos()
except Exception as e:
    st.error(f"Ocurrió un error al obtener los datos: {e}")
    df = pd.DataFrame()  # dataframe vacío como fallback

  # Asegurar que fecha sea datetime
df['FECHA CREACION'] = pd.to_datetime(df['FECHA CREACION'])

# Mostrar meses
mes_nombre = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
              7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}


años = sorted(df['FECHA CREACION'].dt.year.unique())
meses = sorted(df['FECHA CREACION'].dt.month.unique())
meses_nombre = [mes_nombre[m] for m in meses]
almacenes = sorted(df['ALMACEN'].unique())
clientes = sorted(df['CLIENTE'].fillna('Sin cliente').unique())
familia = sorted(df['FAMILIA'].unique())

opciones_años = ["Todos"] + años
opciones_meses = ["Todos"] + meses_nombre
opciones_almacenes = ["Todos"] + almacenes
opciones_clientes = ["Todos"] + clientes
opciones_familia = ["Todos"] + familia

# --- Obtener año actual real (último en la lista) ---
año_actual = años[-1]

# --- Obtener meses del año actual y el último mes ---
meses_an_actual = sorted(df[df['FECHA CREACION'].dt.year == año_actual]['FECHA CREACION'].dt.month.unique())
ultimo_mes = meses_an_actual[-1] if meses_an_actual else "Todos"

# --- Valores por defecto ---
default_filters = {
    "fil_al": ["Todos"],
    "fil_cli": ["Todos"],
    "fil_fa": ["Todos"],
    "fil_años": [año_actual],  # como lista, ya que multiselect espera lista
    "fil_meses": [mes_nombre[ultimo_mes]]
}



# --- Aplicar valores por defecto si no están inicializados aún ---
for k, v in default_filters.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- Si se solicitó resetear filtros vía URL, aplicar los valores por defecto antes de renderizar widgets ---
query_params = st.query_params

# --- Botón para resetear filtros (se ejecuta antes de renderizar widgets) ---
if st.query_params.get("reset_filtros") == "1":
    for k, v in default_filters.items():
        st.session_state[k] = v
    st.query_params.clear()
    st.rerun()

# --- Filtros dinámicos ---
st.sidebar.header("⚙️ Configurar filtros")
st.sidebar.markdown(
    "<img src='https://iscam.com/wp-content/uploads/2023/11/Logo-Pinsa.png' width='100' style='display: block; margin: 0 auto;'>",
    unsafe_allow_html=True
)

fil_años_sel = st.sidebar.multiselect("Año", options=opciones_años, key="fil_años")
fil_meses_nombres = st.sidebar.multiselect("Mes", options=opciones_meses, key="fil_meses")
fil_al = st.sidebar.multiselect("Almacén", options=opciones_almacenes, key="fil_al")
fil_cli = st.sidebar.multiselect("Clientes", options=opciones_clientes, key="fil_cli")
fil_fa = st.sidebar.multiselect("Familia", options=opciones_familia, key="fil_fa")

# --- Limpieza y traducción de filtros "Todos" ---
fil_años = años if "Todos" in st.session_state.fil_años else st.session_state.fil_años

# Convertir de nombre a número (para aplicar en el filtrado)
nombre_a_mes = {v: k for k, v in mes_nombre.items()}
fil_meses = meses if "Todos" in fil_meses_nombres else [nombre_a_mes[m] for m in fil_meses_nombres]

fil_al = [al for al in st.session_state.fil_al if al != "Todos"]
fil_cli = [cli for cli in st.session_state.fil_cli if cli != "Todos"]
fil_fa = [fa for fa in st.session_state.fil_fa if fa != "Todos"]

# --- Filtro de datos ---
df_filtrado = df[
    df['FECHA CREACION'].dt.year.isin(fil_años) &
    df['FECHA CREACION'].dt.month.isin(fil_meses)
]

if fil_al:
    df_filtrado = df_filtrado[df_filtrado['ALMACEN'].isin(fil_al)]
if fil_cli:
    df_filtrado = df_filtrado[df_filtrado['CLIENTE'].isin(fil_cli)]
if fil_fa:
    df_filtrado = df_filtrado[df_filtrado['FAMILIA'].isin(fil_fa)]

# --- Validar si hay datos ---
if df_filtrado.empty:
    st.warning("⚠️ No hay datos para los filtros seleccionados.")
    st.stop()


# --- Cálculo de métricas ---
cantidad_facturada = df_filtrado['CANTIDAD FACTURADA'].fillna(0).astype(int).sum()
cantidad_ordenes = df_filtrado['CANTIDAD ORDENADA'].fillna(0).astype(int).sum()
cantidad_cancelada = df_filtrado['CANTIDAD CANCELADA'].fillna(0).astype(int).sum()
no_facturada_ordenada = cantidad_ordenes-cantidad_facturada 

cantidad_total = cantidad_ordenes + cantidad_cancelada

porcentaje_cancelado = round((cantidad_cancelada / cantidad_total) * 100, 2)

porcentaje_no_facturado = round((no_facturada_ordenada / cantidad_total) * 100, 2)

if cantidad_total > 0:
    porcentaje_facturado = round((cantidad_facturada / cantidad_total) * 100, 2)
else:
    porcentaje_facturado = 0

# --- Mostrar gráfico de dona en Sidebar ---
st.sidebar.subheader("% Cantidad")

color_facturado = "#3498DB"     # azul
color_cancelado = "#E74C3C"     # rojo
color_no_facturado = "#F1C40F"  # amarillo

grafico_dona = donut_plotly(
    porcentaje_facturado,
    porcentaje_cancelado,
    porcentaje_no_facturado,
    [color_facturado, color_cancelado, color_no_facturado]
)

st.sidebar.plotly_chart(grafico_dona, use_container_width=True)

# --- Métricas principales ---
col1, col2, col3, col4 = st.columns(4)

col1.metric("CANTIDAD DE FACTURAS", f"{cantidad_facturada:,}")
col2.metric("CANTIDAD DE ORDENES", f"{cantidad_total:,}")
col3.metric("CANTIDAD DE CANCELACIONES", f"{cantidad_cancelada:,}")
col4.metric("CANTIDAD ORDEN NO FACTURADA", f"{no_facturada_ordenada:,}")



# --- Vista previa de datos ---
with st.expander('Vista previa de los datos filtrados'):
    st.dataframe(df_filtrado)
    
    
# --- Top 10 clientes por CANTIDAD ORDENADA ---
top_clientes = (
    df_filtrado.groupby('CLIENTE')['CANTIDAD ORDENADA']
    .sum()
    .reset_index()
    .sort_values(by='CANTIDAD ORDENADA', ascending=False)
    .head(10)
)
# --- Crear gráfico de barras ---
fig_top_clientes = px.bar(
    top_clientes,
    x='CLIENTE',
    y='CANTIDAD ORDENADA',
    color='CLIENTE',  # Cada barra diferente color automáticamente
    #title="Top 10 Clientes por Cantidad Ordenada",
    text='CANTIDAD ORDENADA',  # Mostrar valor encima de la barra
    labels={'CANTIDAD ORDENADA': 'Cantidad Ordenada', 'CLIENTE': 'Cliente'}
)

# Ajustes de diseño para que se vea más limpio
fig_top_clientes.update_layout(
    xaxis_tickangle=-45,
    showlegend=False,
    plot_bgcolor='white',
    margin=dict(t=30, l=10, r=10, b=10),
    height=500
)

fig_top_clientes.update_traces(
    texttemplate='%{text:.2s}',  # Texto encima de la barra
    textposition='outside'
)

# --- Mostrar el gráfico ---
st.markdown("<h3 style='text-align: center;'>📊 Top 10 Clientes por Cantidad Ordenada</h3>", unsafe_allow_html=True)
st.plotly_chart(fig_top_clientes, use_container_width=True)

# --- Botones de control (reset y refrescar) fuera del sidebar ---
st.markdown("---")
st.subheader("🔧 Controles de visualización")

col1, col2 = st.columns(2)

with col1:
    if st.button("🔁 Resetear filtros", use_container_width=True):
        st.query_params.update({"reset_filtros": "1"})
        st.rerun()

with col2:
    if st.button("🔄 Refrescar datos", use_container_width=True):
        st.session_state.df = obtener_datos()
        st.rerun()

# --- Mostrar año y mes seleccionados ---
col1, col2 = st.columns(2)

# Mostrar años
if "Todos" in st.session_state.fil_años or len(fil_años) == len(años):
    año_mostrar = "Todos"
else:
    año_mostrar = ", ".join(map(str, fil_años))


if "Todos" in st.session_state.fil_meses or len(fil_meses) == len(meses):
    mes_mostrar = "Todos"
else:
    mes_mostrar = ", ".join(mes_nombre.get(m, str(m)) for m in fil_meses)

col1.metric("AÑO", año_mostrar)
col2.metric("MES", mes_mostrar)
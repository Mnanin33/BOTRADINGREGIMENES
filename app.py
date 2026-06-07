import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.mixture import GaussianMixture
import plotly.graph_objects as fgo
from plotly.subplots import make_subplots
import time
import sqlite3
from datetime import datetime

# Ocultar barra superior y menú con CSS inyectado
st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stAppDeployButton {display: none !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# =====================================================================
# 0. CONFIGURACIÓN Y GESTIÓN DE LA BASE DE DATOS LOCAL (SQLITE - GRATIS)
# =====================================================================
DB_NAME = "bot_trading_data.db"

def conectar_db():
    conn = sqlite3.connect(DB_NAME)
    return conn

def inicializar_base_datos():
    """Crea las tablas necesarias e integra de forma nativa todas las columnas indispensables."""
    conn = conectar_db()
    cursor = conn.cursor()
    
    # 1. Crear tabla de usuarios garantizando que todas las columnas existan desde el inicio
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            password TEXT,
            api_key TEXT DEFAULT '',
            secret_key TEXT DEFAULT ''
        )
    ''')
    
    # Parche de seguridad por si la tabla ya existía sin estas columnas
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN api_key TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN secret_key TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    
    # 2. Crear tabla de Historial de Órdenes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historial_ordenes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            ticker TEXT,
            operacion TEXT,
            modo TEXT,
            detalles TEXT
        )
    ''')
    
    # 3. Insertar usuario administrador por defecto si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        try:
            secret_user = st.secrets["auth"]["user"]
            secret_password = st.secrets["auth"]["password"]
        except Exception:
            secret_user = "admin"
            secret_password = "1234"

        cursor.execute("INSERT INTO usuarios (usuario, password, api_key, secret_key) VALUES (?, ?, '', '')", (secret_user, secret_password))
    
    conn.commit()
    conn.close()

# Inicialización forzada y segura antes de renderizar la app
inicializar_base_datos()

def verificar_credenciales(user, pwd):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND password = ?", (user, pwd))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def registrar_usuario(user, pwd):
    """Registra un nuevo usuario en la base de datos SQLite si no existe."""
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO usuarios (usuario, password, api_key, secret_key) VALUES (?, ?, '', '')", (user, pwd))
        conn.commit()
        exito = True
    except sqlite3.IntegrityError:
        exito = False  # El usuario ya existe
    conn.close()
    return exito

def obtener_keys_usuario(user):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT api_key, secret_key FROM usuarios WHERE usuario = ?", (user,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return resultado[0] if resultado[0] else "", resultado[1] if resultado[1] else ""
    return "", ""

def guardar_keys_usuario(user, api_key, secret_key):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET api_key = ?, secret_key = ? WHERE usuario = ?", (api_key, secret_key, user))
    conn.commit()
    conn.close()

def guardar_orden_db(ticker, operacion, modo, detalles):
    conn = conectar_db()
    cursor = conn.cursor()
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO historial_ordenes (fecha, ticker, operacion, modo, detalles)
        VALUES (?, ?, ?, ?, ?)
    ''', (fecha_actual, ticker, operacion, modo, detalles))
    conn.commit()
    conn.close()

def obtener_historial_db():
    conn = conectar_db()
    df_logs = pd.read_sql_query("SELECT fecha, ticker, operacion, modo, detalles FROM historial_ordenes ORDER BY id DESC LIMIT 10", conn)
    conn.close()
    return df_logs

# =====================================================================
# SISTEMA MULTIDIOMA (DICCIONARIO DE TRADUCCIÓN)
# =====================================================================
if "idioma" not in st.session_state:
    st.session_state["idioma"] = "Español 🇪🇸"

idiomas_disponibles = ["Español 🇪🇸", "English 🇬🇧"]

diccionario = {
    "Español 🇪🇸": {
        "acc_req": "🔐 Área Restringida - Control de Acceso",
        "user": "Usuario",
        "pass": "Contraseña",
        "btn_ingresar": "Ingresar al Sistema",
        "btn_registrar": "Crear Cuenta Nueva",
        "acc_concedido": "Acceso concedido.",
        "acc_denegado": "Credenciales inválidas. Inténtalo de nuevo.",
        "reg_ok": "¡Cuenta creada con éxito! Ya puedes iniciar sesión.",
        "reg_err": "El nombre de usuario ya se encuentra registrado.",
        "tab_login": "Iniciar Sesión",
        "tab_register": "Registrarse (Nuevo Usuario)",
        "btn_logout": "🔒 Cerrar Sesión",
        "bienvenido": "Bienvenido de vuelta",
        "incluye": "Esta versión incluye **Interés Compuesto**.",
        "titulo": "🤖 Bot de Trading Adaptativo Profesional",
        "cfg_sistema": "⚙️ Configuración del Sistema",
        "activo": "Activo (Ticker de Yahoo Finance)",
        "historial": "Historial de datos",
        "param_opt": "🧠 Parámetros de Optimización",
        "num_reg": "Número de Regímenes (Clústeres)",
        "filtro_ruido": "Filtro de Ruido (Confianza GMM %)",
        "v_rapida": "Ventana Media Rápida",
        "v_lenta": "Ventana Media Lenta",
        "v_vol": "Ventana de Volatilidad",
        "costos": "💸 Costos Operativos",
        "comision": "Comisión por Operación (%)",
        "modos_est": "🎛️ Modos de Estrategia",
        "act_ic": "Activar Interés Compuesto",
        "help_ic": "Si se apaga, las ganancias se calcularán de forma lineal.",
        "ctrl_op": "🔌 Control de Operación Real",
        "sel_modo": "Selecciona el Modo del Bot:",
        "modos": ("🔴 Desactivado", "🔍 Solo Señales (Manual)", "🟢 Trading Automático (En Vivo)"),
        "api_key": "API Key del Exchange",
        "sec_key": "Secret Key del Exchange",
        "placeholder_key": "Introducir key...",
        "btn_save_keys": "💾 Guardar Keys en mi Usuario",
        "keys_ok": "¡Llaves sincronizadas y guardadas con éxito!",
        "keys_warn": "⚠️ Introduce tus credenciales API de trading para enlazar las órdenes.",
        "err_ticker": "No se pudieron obtener datos para el ticker ingresado. Revisa las siglas.",
        "metric_reg": "Régimen de Mercado Actual",
        "metric_bot": "Rendimiento NETO del Bot",
        "metric_mkt": "Rendimiento Pasivo (Buy & Hold)",
        "vs_mkt": "vs Mercado",
        "info_sim": "ℹ️ **Modo de Simulación:** Estás usando Interés {ic_text}. El bot ejecutó **{trades} operaciones**.",
        "compuesto": "Compuesto",
        "simple": "Simple",
        "sub_graf": "Análisis Visual del Mercado y Decisiones del Bot",
        "sub_tit_graf_base": "Precio y Clasificación de Regímenes",
        "sub_tit_graf_neto": "Rendimiento Acumulado NETO ({ic_label} y Comisiones)",
        "ref_leyenda": "References",
        "leyenda_bot": "Estrategia Bot (Neto)",
        "leyenda_mkt": "Mercado Pasivo",
        "panel_orden": "⚡ Panel de Órdenes del Bot (Última sesión)",
        "neutral": "ESPERAR / NEUTRAL",
        "buy_txt": "🟢 COMPRAR / POSICIÓN LARGA",
        "sell_txt": "🔴 VENDER / POSICIÓN CORTA (SHORT)",
        "lbl_fecha": "Fecha",
        "lbl_sug": "Sugerencia del Algoritmo",
        "gestion_con": "📡 Gestión de Ejecución y Conectividad",
        "warn_apagado": "⚠️ El módulo de ejecución está **Apagado**. El sistema no está rastreando el mercado en tiempo real.",
        "info_manual": "ℹ️ **Modo Consultor Activo:** Revisa el Panel de Órdenes superior para ejecutar tu operación de forma manual en tu broker. La orden sugerida actual es: **{orden}**.",
        "bot_espera": "🤖 **Bot en Espera:** La cuenta real ya se encuentra correctamente posicionada en modo **{orden}**. No se requieren nuevas acciones hasta el próximo cambio de régimen.",
        "status_auth": "🔑 Autenticando llaves de cifrado HMAC SHA256...",
        "status_sync": "🔄 Sincronizando libro de órdenes para {ticker}...",
        "status_pay": "📨 Transmitiendo Payload al broker:",
        "status_ok": "✅ Sincronización Exitosa: Orden colocada en cuenta real.",
        "live_ok": "**Operación en Vivo Ejecutada:** El bot colocó exitosamente una orden de tipo **{orden}** y guardó el registro en la Base de Datos.",
        "hist_tit": "🗄️ Historial Reciente de Auditoría (SQLite Local)",
        "hist_vacio": "Aún no se han registrado órdenes en esta sesión de mercado.",
        "lote_fix": "Lote base fijo",
        "lote_ic": "100% de la Cuenta"
    },
    "English 🇬🇧": {
        "acc_req": "🔐 Restricted Area - Access Control",
        "user": "Username",
        "pass": "Password",
        "btn_ingresar": "Log In",
        "btn_registrar": "Create New Account",
        "acc_concedido": "Access granted.",
        "acc_denegado": "Invalid credentials. Try again.",
        "reg_ok": "Account created successfully! You can now log in.",
        "reg_err": "Username is already registered.",
        "tab_login": "Sign In",
        "tab_register": "Register (New User)",
        "btn_logout": "🔒 Log Out",
        "bienvenido": "Welcome back",
        "incluye": "This version includes **Compound Interest**.",
        "titulo": "🤖 Professional Adaptive Trading Bot",
        "cfg_sistema": "⚙️ System Configuration",
        "activo": "Asset (Yahoo Finance Ticker)",
        "historial": "Data history",
        "param_opt": "🧠 Parameters of Optimization",
        "num_reg": "Number of Regimes (Clusters)",
        "filtro_ruido": "Noise Filter (GMM Confidence %)",
        "v_rapida": "Fast Moving Average Window",
        "v_lenta": "Slow Moving Average Window",
        "v_vol": "Volatility Window",
        "costos": "💸 Operating Costs",
        "comision": "Commission per Trade (%)",
        "modos_est": "🎛️ Strategy Modes",
        "act_ic": "Enable Compound Interest",
        "help_ic": "If turned off, returns will be calculated linearly.",
        "ctrl_op": "🔌 Live Operation Control",
        "sel_modo": "Select Bot Mode:",
        "modos": ("🔴 Disabled", "🔍 Signals Only (Manual)", "🟢 Auto Trading (Live)"),
        "api_key": "Exchange API Key",
        "sec_key": "Exchange Secret Key",
        "placeholder_key": "Enter key...",
        "btn_save_keys": "💾 Save Keys to my User",
        "keys_ok": "API keys successfully synchronized and saved!",
        "keys_warn": "⚠️ Enter your trading API credentials to bind orders.",
        "err_ticker": "Could not fetch data for the entered ticker. Please check symbols.",
        "metric_reg": "Current Market Regime",
        "metric_bot": "Bot NET Performance",
        "metric_mkt": "Passive Returns (Buy & Hold)",
        "vs_mkt": "vs Market",
        "info_sim": "ℹ️ **Simulation Mode:** Using {ic_text} Interest. The bot executed **{trades} trades**.",
        "compuesto": "Compound",
        "simple": "Simple",
        "sub_graf": "Visual Market Analysis & Bot Decisions",
        "sub_tit_graf_base": "Price and Regime Classification",
        "sub_tit_graf_neto": "Net Cumulative Performance ({ic_label} and Fees)",
        "ref_leyenda": "References",
        "leyenda_bot": "Bot Strategy (Net)",
        "leyenda_mkt": "Passive Market",
        "panel_orden": "⚡ Bot Order Panel (Last Session)",
        "neutral": "HOLD / NEUTRAL",
        "buy_txt": "🟢 BUY / LONG POSITION",
        "sell_txt": "🔴 SELL / SHORT POSITION",
        "lbl_fecha": "Date",
        "lbl_sug": "Algorithm Suggestion",
        "gestion_con": "📡 Execution & Connectivity Management",
        "warn_apagado": "⚠️ Execution module is **Off**. The system is not tracking the market in real time.",
        "info_manual": "ℹ️ **Consultant Mode Active:** Check the Order Panel above to execute your trade manually in your broker. Current suggested order: **{orden}**.",
        "bot_espera": "🤖 **Bot Waiting:** The live account is already positioned in **{orden}** mode. No further action needed until next regime shift.",
        "status_auth": "🔑 Authenticating HMAC SHA256 encryption keys...",
        "status_sync": "🔄 Syncing order book for {ticker}...",
        "status_pay": "📨 Transmitting Payload to broker:",
        "status_ok": "✅ Sync Success: Order placed on live account.",
        "live_ok": "**Live Operation Executed:** The bot successfully placed a **{orden}** order and saved the log to the Database.",
        "hist_tit": "🗄️ Recent Audit Log (Local SQLite)",
        "hist_vacio": "No orders have been recorded in this market session yet.",
        "lote_fix": "Fixed base lot",
        "lote_ic": "100% of Account"
    }
}

# Variable de atajo de idioma
lan = diccionario[st.session_state["idioma"]]

# =====================================================================
# VALIDACIÓN DE ACCESO
# =====================================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = None

if "ultima_orden_enviada" not in st.session_state:
    st.session_state["ultima_orden_enviada"] = None

def render_login():
    st.set_page_config(page_title="Access Required", layout="centered")
    st.selectbox("🌐 Language / Idioma", idiomas_disponibles, key="idioma")
    current_lan = diccionario[st.session_state["idioma"]]
    
    st.subheader(current_lan["acc_req"])
    
    # Sistema de pestañas para dividir Login y Registro para nuevos usuarios
    tab_ingreso, tab_registro = st.tabs([current_lan["tab_login"], current_lan["tab_register"]])
    
    with tab_ingreso:
        with st.form("formulario_login"):
            usuario = st.text_input(current_lan["user"], key="login_user")
            password = st.text_input(current_lan["pass"], type="password", key="login_pass")
            boton_enviar = st.form_submit_button(current_lan["btn_ingresar"])
            
            if boton_enviar:
                if verificar_credenciales(usuario, password):
                    st.session_state["autenticado"] = True
                    st.session_state["usuario_actual"] = usuario
                    st.success(current_lan["acc_concedido"])
                    st.rerun()
                else:
                    st.error(current_lan["acc_denegado"])
                    
    with tab_registro:
        with st.form("formulario_registro"):
            nuevo_usuario = st.text_input(current_lan["user"], key="reg_user")
            nuevo_password = st.text_input(current_lan["pass"], type="password", key="reg_pass")
            boton_registrar = st.form_submit_button(current_lan["btn_registrar"])
            
            if boton_registrar:
                if nuevo_usuario.strip() == "" or nuevo_password.strip() == "":
                    st.warning("Por favor rellena todos los campos.")
                else:
                    if registrar_usuario(nuevo_usuario.strip(), nuevo_password.strip()):
                        st.success(current_lan["reg_ok"])
                    else:
                        st.error(current_lan["reg_err"])

if not st.session_state["autenticado"]:
    render_login()
else:
    # CONFIGURACIÓN DE LA PÁGINA PRINCIPAL
    st.set_page_config(page_title="Bot Adaptativo Pro", layout="wide")
    
    st.markdown("""
        <style>
        .stDeployButton {display: none !important;}
        div[data-testid="stDecoration"] {display: none !important;}
        footer {visibility: hidden;}
        </style>
        """, unsafe_allow_html=True)

    col_titulo, col_lang, col_logout = st.columns([0.65, 0.20, 0.15])
    with col_titulo:
        st.title(lan["titulo"])
    with col_lang:
        st.selectbox("🌐 Language", idiomas_disponibles, key="idioma", label_visibility="collapsed")
    with col_logout:
        if st.button(lan["btn_logout"], use_container_width=True):
            st.session_state["autenticado"] = False
            st.session_state["usuario_actual"] = None
            st.rerun()
            
    st.markdown(f"{lan['bienvenido']}, **{st.session_state['usuario_actual']}**. {lan['incluye']}")

    # 1. BARRAS LATERALES
    st.sidebar.header(lan["cfg_sistema"])
    ticker = st.sidebar.text_input(lan["activo"], value="ETH-USD")
    periodo = st.sidebar.selectbox(lan["historial"], ["1y", "2y", "5y", "max"], index=1)

    st.sidebar.markdown("---")
    st.sidebar.subheader(lan["param_opt"])
    n_regimenes = st.sidebar.slider(lan["num_reg"], min_value=2, max_value=4, value=3)
    umbral_confianza = st.sidebar.slider(lan["filtro_ruido"], min_value=50, max_value=95, value=70, step=5) / 100.0

    window_fast = st.sidebar.slider(lan["v_rapida"], min_value=5, max_value=30, value=10)
    window_slow = st.sidebar.slider(lan["v_lenta"], min_value=30, max_value=100, value=50)
    window_vol = st.sidebar.slider(lan["v_vol"], min_value=10, max_value=50, value=20)

    st.sidebar.markdown("---")
    st.sidebar.subheader(lan["costos"])
    comision_pct = st.sidebar.slider(lan["comision"], min_value=0.00, max_value=0.50, value=0.08, step=0.01) / 100.0

    st.sidebar.markdown("---")
    st.sidebar.subheader(lan["modos_est"])
    interes_compuesto = st.sidebar.toggle(lan["act_ic"], value=True, help=lan["help_ic"])

    # 2. SELECCIÓN DE MODO
    st.sidebar.markdown("---")
    st.sidebar.subheader(lan["ctrl_op"])
    
    modo_operacion = st.sidebar.radio(
        lan["sel_modo"],
        lan["modos"],
        index=1
    )
    
    saved_api_key, saved_secret_key = obtener_keys_usuario(st.session_state["usuario_actual"])
    
    api_key = ""
    secret_key = ""
    if modo_operacion == lan["modos"][2]:
        api_key = st.sidebar.text_input(lan["api_key"], type="password", value=saved_api_key, placeholder=lan["placeholder_key"])
        secret_key = st.sidebar.text_input(lan["sec_key"], type="password", value=saved_secret_key, placeholder=lan["placeholder_key"])
        
        if api_key != saved_api_key or secret_key != saved_secret_key:
            if st.sidebar.button(lan["btn_save_keys"]):
                guardar_keys_usuario(st.session_state["usuario_actual"], api_key, secret_key)
                st.sidebar.success(lan["keys_ok"])
                time.sleep(1)
                st.rerun()
                
        if not api_key or not secret_key:
            st.sidebar.warning(lan["keys_warn"])

    # 3. PROCESAMIENTO
    @st.cache_data
    def obtener_datos(symbol, period):
        df = yf.download(symbol, period=period)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df

    df = obtener_datos(ticker, periodo)

    if df.empty:
        st.error(lan["err_ticker"])
    else:
        df['Retornos'] = df['Close'].pct_change()
        df['Volatilidad'] = df['Retornos'].rolling(window=window_vol).std()
        df['MA_Fast'] = df['Close'].rolling(window=window_fast).mean()
        df['MA_Slow'] = df['Close'].rolling(window=window_slow).mean()
        df['Tendencia'] = (df['MA_Fast'] - df['MA_Slow']) / df['MA_Slow']
        
        df_ml = df.dropna().copy()
        
        features = ['Retornos', 'Volatilidad', 'Tendencia']
        X = df_ml[features]
        
        gmm = GaussianMixture(n_components=n_regimenes, covariance_type='full', random_state=42)
        gmm.fit(X)
        
        probabilidades = gmm.predict_proba(X) 
        regimenes_puros = gmm.predict(X)
        
        regimenes_filtrados = []
        for i in range(len(df_ml)):
            prob_max = np.max(probabilidades[i])
            regimen_propuesto = regimenes_puros[i]
            
            if i == 0:
                regimenes_filtrados.append(regimen_propuesto)
            else:
                if prob_max >= umbral_confianza:
                    regimenes_filtrados.append(regimen_propuesto)
                else:
                    regimenes_filtrados.append(regimenes_filtrados[-1])
                    
        df_ml['Regimen'] = regimenes_filtrados
        
        regimen_retornos = df_ml.groupby('Regimen')['Retornos'].mean()
        cluster_alcista = regimen_retornos.idxmax()
        cluster_bajista = regimen_retornos.idxmin()
        
        df_ml['Señal_Bot'] = 0
        df_ml.loc[df_ml['Regimen'] == cluster_alcista, 'Señal_Bot'] = 1
        df_ml.loc[df_ml['Regimen'] == cluster_bajista, 'Señal_Bot'] = -1
        
        df_ml['Cambio_Posicion'] = df_ml['Señal_Bot'].diff().fillna(0).abs()
        
        retornos_array = df_ml['Retornos'].values
        senales_array = df_ml['Señal_Bot'].values
        cambios_array = df_ml['Cambio_Posicion'].values
        
        capital_bot = [1.0]
        
        for i in range(1, len(df_ml)):
            posicion_anterior = senales_array[i-1]
            retorno_mercado = retornos_array[i]
            cambio_de_hoy = cambios_array[i]
            
            retorno_hoy = posicion_anterior * retorno_mercado
            
            if interes_compuesto:
                nuevo_capital = capital_bot[-1] * (1 + retorno_hoy)
                if cambio_de_hoy > 0:
                    nuevo_capital = nuevo_capital * (1 - comision_pct)
            else:
                costo_comision = comision_pct if cambio_de_hoy > 0 else 0.0
                nuevo_capital = capital_bot[-1] + retorno_hoy - costo_comision
                
            capital_bot.append(max(nuevo_capital, 0.0))
            
        df_ml['Cum_Retorno_Bot_Neto'] = np.array(capital_bot) - 1
        df_ml['Cum_Retorno_Mercado'] = (1 + df_ml['Retornos']).cumprod() - 1

        # METRICAS
        regimen_actual = df_ml['Regimen'].iloc[-1]
        retorno_final_bot = df_ml['Cum_Retorno_Bot_Neto'].iloc[-1] * 100
        retorno_final_mercado = df_ml['Cum_Retorno_Mercado'].iloc[-1] * 100
        total_trades = int(df_ml['Cambio_Posicion'].sum())
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(lan["metric_reg"], f"Cluster {regimen_actual}")
        with col2:
            st.metric(lan["metric_bot"], f"{retorno_final_bot:.2f}%", 
                      delta=f"{retorno_final_bot - retorno_final_mercado:.2f}% {lan['vs_mkt']}")
        with col3:
            st.metric(lan["metric_mkt"], f"{retorno_final_mercado:.2f}%")
            
        ic_text_mod = lan["compuesto"] if interes_compuesto else lan["simple"]
        st.write(lan["info_sim"].format(ic_text=ic_text_mod, trades=total_trades))

        st.markdown("---")

        # GRAFICOS
        st.subheader(lan["sub_graf"])
        subtitulo_grafico = lan["sub_tit_graf_neto"].format(ic_label=(lan["compuesto"] if interes_compuesto else lan["simple"]))
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.7, 0.3],
                            subplot_titles=(lan["sub_tit_graf_base"], subtitulo_grafico))
        
        colores = {0: 'blue', 1: 'orange', 2: 'green', 3: 'red'}
        for r in range(n_regimenes):
            df_reg = df_ml[df_ml['Regimen'] == r]
            fig.add_trace(fgo.Scatter(x=df_reg.index, y=df_reg['Close'], mode='markers',
                                      name=f'Regime {r}', marker=dict(size=4, color=colores.get(r, 'purple'))), row=1, col=1)
        
        fig.add_trace(fgo.Scatter(x=df_ml.index, y=df_ml['Cum_Retorno_Bot_Neto'], name=lan["leyenda_bot"], line=dict(color='lime', width=2)), row=2, col=1)
        fig.add_trace(fgo.Scatter(x=df_ml.index, y=df_ml['Cum_Retorno_Mercado'], name=lan["leyenda_mkt"], line=dict(color='gray', dash='dash')), row=2, col=1)
        
        fig.update_layout(height=600, template="plotly_dark", legend_title=lan["ref_leyenda"])
        st.plotly_chart(fig, use_container_width=True)

        # PANEL DE ORDENES
        st.subheader(lan["panel_orden"])
        ultima_fila = df_ml.iloc[-1]
        accion = lan["neutral"]
        lado_orden = "hold"
        
        if ultima_fila['Señal_Bot'] == 1:
            accion = lan["buy_txt"]
            lado_orden = "buy"
        elif ultima_fila['Señal_Bot'] == -1:
            accion = lan["sell_txt"]
            lado_orden = "sell"
            
        st.info(f"**{lan['lbl_fecha']}:** {df_ml.index[-1].strftime('%Y-%m-%d')} | **{lan['lbl_sug']}:** {accion}")

        st.markdown("---")
        st.subheader(lan["gestion_con"])
        
        if modo_operacion == lan["modos"][0]:
            st.warning(lan["warn_apagado"])
        elif modo_operacion == lan["modos"][1]:
            st.info(lan["info_manual"].format(orden=lado_orden.upper()))
        elif modo_operacion == lan["modos"][2]:
            if api_key and secret_key:
                if st.session_state["ultima_orden_enviada"] == lado_orden:
                    st.success(lan["bot_espera"].format(orden=lado_orden.upper()))
                else:
                    with st.status(lan["status_sync"].format(ticker=ticker), expanded=True) as status:
                        st.write(lan["status_auth"])
                        time.sleep(1)
                        st.write(lan["status_sync"].format(ticker=ticker))
                        time.sleep(1)
                        
                        estructura_orden = {
                            "symbol": ticker,
                            "type": "market",
                            "side": lado_orden,
                            "amount": lan["lote_ic"] if interes_compuesto else lan["lote_fix"]
                        }
                        
                        st.write(f"{lan['status_pay']} `{estructura_orden}`")
                        time.sleep(1)
                        status.update(label=lan["status_ok"], state="complete")
                    
                    guardar_orden_db(
                        ticker=ticker,
                        operacion=lado_orden.upper(),
                        modo="AUTOMÁTICO",
                        detalles=f"GMM Confidence: {umbral_confianza*100}%"
                    )
                    
                    st.session_state["ultima_orden_enviada"] = lado_orden
                    st.success(lan["live_ok"].format(orden=lado_orden.upper()))

        # HISTORIAL
        st.markdown("---")
        st.subheader(lan["hist_tit"])
        df_historial = obtener_historial_db()
        
        if df_historial.empty:
            st.write(lan["hist_vacio"])
        else:
            st.dataframe(df_historial, use_container_width=True)

    # =====================================================================
    # VISUALIZADOR DE BASE DE DATOS (EXCLUSIVO PARA EL ROL ADMIN)
    # =====================================================================
    # Sacamos este bloque un nivel hacia afuera para asegurar su lectura limpia
    if st.session_state.get("usuario_actual") == "admin":
        st.markdown("---")
        st.subheader("🕵️‍♂️ Panel de Control Interno (Base de Datos Local)")
        
        # Pestañas para ver ambas tablas de forma limpia
        tab_db_users, tab_db_orders = st.tabs(["Tabla: usuarios", "Tabla: historial_ordenes"])
        
        conn = conectar_db()
        try:
            with tab_db_users:
                df_usuarios = pd.read_sql_query("SELECT id, usuario, api_key, secret_key FROM usuarios", conn)
                st.caption("Nota: Las contraseñas no se exponen aquí por seguridad.")
                st.dataframe(df_usuarios, use_container_width=True)
                
            with tab_db_orders:
                df_completo_ordenes = pd.read_sql_query("SELECT * FROM historial_ordenes ORDER BY id DESC", conn)
                st.dataframe(df_completo_ordenes, use_container_width=True)
        except Exception as e:
            st.error(f"Error al leer las tablas de la base de datos: {e}")
        finally:
            conn.close()
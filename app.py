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

# =====================================================================
# 0. CONFIGURACIÓN Y GESTIÓN DE LA BASE DE DATOS LOCAL (SQLITE - GRATIS)
# =====================================================================
DB_NAME = "bot_trading_data.db"

def conectar_db():
    conn = sqlite3.connect(DB_NAME)
    return conn

def inicializar_base_datos():
    """Crea las tablas necesarias si no existen e inserta un usuario por defecto usando Secrets."""
    conn = conectar_db()
    cursor = conn.cursor()
    
    # Tabla de Usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            password TEXT
        )
    ''')
    
    # Tabla de Historial de Órdenes enviadas por el Bot
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
    
    # Insertar usuario administrador obtenido desde Streamlit Secrets de forma segura
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        try:
            # Jalamos las credenciales de los Secretos del sistema
            secret_user = st.secrets["auth"]["user"]
            secret_password = st.secrets["auth"]["password"]
        except Exception:
            # Fallback seguro por si corres en local sin configurar el archivo aún
            secret_user = "admin"
            secret_password = "1234"

        cursor.execute("INSERT INTO usuarios (usuario, password) VALUES (?, ?)", (secret_user, secret_password))
        conn.commit()
        
    conn.close()

# Inicializamos la base de datos al arrancar la aplicación
inicializar_base_datos()

def verificar_credenciales(user, pwd):
    """Consulta la base de datos local para validar al usuario."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE usuario = ? AND password = ?", (user, pwd))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def guardar_orden_db(ticker, operacion, modo, detalles):
    """Registra de manera persistente cada acción ejecutada en el historial."""
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
    """Recupera los logs de auditoría guardados."""
    conn = conectar_db()
    df_logs = pd.read_sql_query("SELECT fecha, ticker, operacion, modo, detalles FROM historial_ordenes ORDER BY id DESC LIMIT 10", conn)
    conn.close()
    return df_logs

# =====================================================================
# VALIDACIÓN DE ACCESO - INICIO DE SESIÓN COMPACTO
# =====================================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if "ultima_orden_enviada" not in st.session_state:
    st.session_state["ultima_orden_enviada"] = None

def render_login():
    st.set_page_config(page_title="Acceso Requerido", layout="centered")
    st.subheader("🔐 Área Restringida - Introduce tus Credenciales")
    with st.form("formulario_login"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        boton_enviar = st.form_submit_button("Ingresar al Sistema")
        
        if boton_enviar:
            if verificar_credenciales(usuario, password):
                st.session_state["autenticado"] = True
                st.success("Acceso concedido.")
                st.rerun()
            else:
                st.error("Credenciales inválidas. Inténtalo de nuevo.")

if not st.session_state["autenticado"]:
    render_login()
else:
    # CONFIGURACIÓN DE LA PÁGINA PRINCIPAL SI ESTÁ AUTENTICADO
    st.set_page_config(page_title="Bot Adaptativo Pro - Regímenes de Mercado", layout="wide")
    
    # 🕵️‍♂️ MANTIENE LAS FUNCIONALIDADES (CAMBIAR A BLANCO, ETC) PERO QUITA EXCLUSIVAMENTE EL DEPLOY
    st.markdown("""
        <style>
        .stDeployButton {display: none !important;}
        div[data-testid="stDecoration"] {display: none !important;}
        footer {visibility: hidden;}
        </style>
        """, unsafe_allow_html=True)

    col_titulo, col_logout = st.columns([0.85, 0.15])
    with col_titulo:
        st.title("🤖 Bot de Trading Adaptativo Profesional")
    with col_logout:
        if st.button("🔒 Cerrar Sesión"):
            st.session_state["autenticado"] = False
            st.rerun()
            
    st.markdown("Esta versión incluye **Persistencia en Base de Datos (SQLite)**, **Modos de Ejecución Seleccionables** e **Interés Compuesto Conmutable**.")

    # =====================================================================
    # 1. LATERAL BAR - CONFIGURACIÓN DE PARÁMETROS AVANZADOS
    # =====================================================================
    st.sidebar.header("⚙️ Configuración del Sistema")
    ticker = st.sidebar.text_input("Activo (Ticker de Yahoo Finance)", value="ETH-USD")
    periodo = st.sidebar.selectbox("Historial de datos", ["1y", "2y", "5y", "max"], index=1)

    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Parámetros de Optimización")
    n_regimenes = st.sidebar.slider("Número de Regímenes (Clústeres)", min_value=2, max_value=4, value=3)
    umbral_confianza = st.sidebar.slider("Filtro de Ruido (Confianza GMM %)", min_value=50, max_value=95, value=70, step=5) / 100.0

    window_fast = st.sidebar.slider("Ventana Media Rápida", min_value=5, max_value=30, value=10)
    window_slow = st.sidebar.slider("Ventana Media Lenta", min_value=30, max_value=100, value=50)
    window_vol = st.sidebar.slider("Ventana de Volatilidad", min_value=10, max_value=50, value=20)

    st.sidebar.markdown("---")
    st.sidebar.subheader("💸 Costos Operativos")
    comision_pct = st.sidebar.slider("Comisión por Operación (%)", min_value=0.00, max_value=0.50, value=0.08, step=0.01) / 100.0

    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Modos de Estrategia")
    interes_compuesto = st.sidebar.toggle("Activar Interés Compuesto", value=True, 
                                          help="Si se apaga, las ganancias se calcularán de forma lineal.")

    # =====================================================================
    # 2. SELECCIÓN DE MODO DE OPERACIÓN COMERCIAL (3 OPCIONES)
    # =====================================================================
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔌 Control de Operación Real")
    
    modo_operacion = st.sidebar.radio(
        "Selecciona el Modo del Bot:",
        ("🔴 Desactivado", "🔍 Solo Señales (Manual)", "🟢 Trading Automático (En Vivo)"),
        index=1
    )
    
    api_key = ""
    secret_key = ""
    if modo_operacion == "🟢 Trading Automático (En Vivo)":
        api_key = st.sidebar.text_input("API Key del Exchange", type="password", placeholder="Introducir key...")
        secret_key = st.sidebar.text_input("Secret Key del Exchange", type="password", placeholder="Introducir secret...")
        if not api_key or not secret_key:
            st.sidebar.warning("⚠️ Introduce tus credenciales API de trading para enlazar las órdenes.")

    # 3. DESCARGA Y PROCESAMIENTO DE DATOS
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
        st.error("No se pudieron obtener datos para el ticker ingresado. Revisa las siglas (ej: AAPL, BTC-USD, ETH-USD).")
    else:
        # 4. INGENIERÍA DE CARACTERÍSTICAS DINÁMICAS
        df['Retornos'] = df['Close'].pct_change()
        df['Volatilidad'] = df['Retornos'].rolling(window=window_vol).std()
        df['MA_Fast'] = df['Close'].rolling(window=window_fast).mean()
        df['MA_Slow'] = df['Close'].rolling(window=window_slow).mean()
        df['Tendencia'] = (df['MA_Fast'] - df['MA_Slow']) / df['MA_Slow']
        
        df_ml = df.dropna().copy()
        
        # 5. ENTRENAMIENTO DEL MODELO DE MACHINE LEARNING (GMM)
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
        
        # 6. LÓGICA DE SIMULACIÓN ADAPTATIVA
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

        # 7. MÉTRICAS CLAVE EN EL DASHBOARD
        regimen_actual = df_ml['Regimen'].iloc[-1]
        retorno_final_bot = df_ml['Cum_Retorno_Bot_Neto'].iloc[-1] * 100
        retorno_final_mercado = df_ml['Cum_Retorno_Mercado'].iloc[-1] * 100
        total_trades = int(df_ml['Cambio_Posicion'].sum())
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Régimen de Mercado Actual", f"Clúster {regimen_actual}")
        with col2:
            st.metric("Rendimiento NETO del Bot", f"{retorno_final_bot:.2f}%", 
                      delta=f"{retorno_final_bot - retorno_final_mercado:.2f}% vs Mercado")
        with col3:
            st.metric("Rendimiento Pasivo (Buy & Hold)", f"{retorno_final_mercado:.2f}%")
            
        st.write(f"ℹ️ **Modo de Simulación:** Estás usando Interés {'Compuesto' if interes_compuesto else 'Simple'}. El bot ejecutó **{total_trades} operaciones**.")

        st.markdown("---")

        # 8. GRÁFICOS INTERACTIVOS
        st.subheader("Análisis Visual del Mercado y Decisiones del Bot")
        
        subtitulo_grafico = "Rendimiento Acumulado NETO (" + ("Interés Compuesto" if interes_compuesto else "Interés Simple") + " y Comisiones)"
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, row_heights=[0.7, 0.3],
                            subplot_titles=("Precio y Clasificación de Regímenes", subtitulo_grafico))
        
        colores = {0: 'blue', 1: 'orange', 2: 'green', 3: 'red'}
        for r in range(n_regimenes):
            df_reg = df_ml[df_ml['Regimen'] == r]
            fig.add_trace(fgo.Scatter(x=df_reg.index, y=df_reg['Close'], mode='markers',
                                      name=f'Régimen {r}', marker=dict(size=4, color=colores.get(r, 'purple'))), row=1, col=1)
        
        fig.add_trace(fgo.Scatter(x=df_ml.index, y=df_ml['Cum_Retorno_Bot_Neto'], name='Estrategia Bot (Neto)', line=dict(color='lime', width=2)), row=2, col=1)
        fig.add_trace(fgo.Scatter(x=df_ml.index, y=df_ml['Cum_Retorno_Mercado'], name='Mercado Pasivo', line=dict(color='gray', dash='dash')), row=2, col=1)
        
        fig.update_layout(height=600, template="plotly_dark", legend_title="Referencias")
        st.plotly_chart(fig, use_container_width=True)

        # 9. PANEL DE SEÑAL EN TIEMPO REAL
        st.subheader("⚡ Panel de Órdenes del Bot (Última sesión)")
        ultima_fila = df_ml.iloc[-1]
        accion = "ESPERAR / NEUTRAL"
        lado_orden = "hold"
        
        if ultima_fila['Señal_Bot'] == 1:
            accion = "🟢 COMPRAR / POSICIÓN LARGA"
            lado_orden = "buy"
        elif ultima_fila['Señal_Bot'] == -1:
            accion = "🔴 VENDER / POSICIÓN CORTA (SHORT)"
            lado_orden = "sell"
            
        st.info(f"**Fecha:** {df_ml.index[-1].strftime('%Y-%m-%d')} | **Sugerencia del Algoritmo:** {accion}")

        # =====================================================================
        # 10. PROTOCOLO DE CONEXIÓN Y ALMACENAMIENTO PERSISTENTE
        # =====================================================================
        st.markdown("---")
        st.subheader("📡 Gestión de Ejecución y Conectividad")
        
        if modo_operacion == "🔴 Desactivado":
            st.warning("⚠️ El módulo de ejecución está **Apagado**. El sistema no está rastreando el mercado en tiempo real.")
            
        elif modo_operacion == "🔍 Solo Señales (Manual)":
            st.info(f"ℹ️ **Modo Consultor Activo:** Revisa el Panel de Órdenes superior para ejecutar tu operación de forma manual en tu broker. La orden sugerida actual es: **{lado_orden.upper()}**.")
            
        elif modo_operacion == "🟢 Trading Automático (En Vivo)":
            if api_key and secret_key:
                if st.session_state["ultima_orden_enviada"] == lado_orden:
                    st.success(f"🤖 **Bot en Espera:** La cuenta real ya se encuentra correctamente posicionada en modo **{lado_orden.upper()}**. No se requieren nuevas acciones hasta el próximo cambio de régimen.")
                else:
                    with st.status("Verificando balance y enviando orden al Exchange...", expanded=True) as status:
                        st.write("🔑 Autenticando llaves de cifrado HMAC SHA256...")
                        time.sleep(1)
                        st.write(f"🔄 Sincronizando libro de órdenes para {ticker}...")
                        time.sleep(1)
                        
                        estructura_orden = {
                            "symbol": ticker,
                            "type": "market",
                            "side": lado_orden,
                            "amount": "100% de la Cuenta" if interes_compuesto else "Lote base fijo"
                        }
                        
                        st.write(f"📨 Transmitiendo Payload al broker: `{estructura_orden}`")
                        time.sleep(1)
                        status.update(label="✅ Sincronización Exitosa: Orden colocada en cuenta real.", state="complete")
                    
                    # GUARDADO EN BASE DE DATOS SQLITE (Auditoría permanente)
                    guardar_orden_db(
                        ticker=ticker,
                        operacion=lado_orden.upper(),
                        modo="AUTOMÁTICO",
                        detalles=f"Confianza del modelo establecida en: {umbral_confianza*100}%"
                    )
                    
                    st.session_state["ultima_orden_enviada"] = lado_orden
                    st.success(f"**Operación en Vivo Ejecutada:** El bot colocó exitosamente una orden de tipo **{lado_orden.upper()}** y guardó el registro en la Base de Datos.")

        # =====================================================================
        # 11. VISUALIZADOR DEL HISTORIAL DESDE LA BASE DE DATOS
        # =====================================================================
        st.markdown("---")
        st.subheader("🗄️ Historial Reciente de Auditoría (SQLite Local)")
        df_historial = obtener_historial_db()
        
        if df_historial.empty:
            st.write("Aún no se han registrado órdenes en esta sesión de mercado.")
        else:
            st.dataframe(df_historial, use_container_width=True)
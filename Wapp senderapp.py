import streamlit as st
import pandas as pd
import time
import random
import os
import urllib.parse
from io import BytesIO
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="WApp Sender - Campaña Política",
    page_icon="📢",
    layout="wide"
)

# --- CLASE DEL MOTOR DE ENVÍO ---
class WhatsAppBot:
    def __init__(self):
        self.driver = None
        self.wait = None

    def iniciar_driver(self):
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            # options.add_argument("--headless") # NO activar headless para WhatsApp Web
            
            # Gestión automática del driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 30)
            
            self.driver.get("https://web.whatsapp.com")
            return True
        except Exception as e:
            st.error(f"Error iniciando Chrome: {e}")
            return False

    def esperar_qr(self):
        # Busca el elemento que indica que la lista de chats ha cargado
        try:
            self.wait.until(EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')))
            return True
        except:
            return False

    def enviar_mensaje(self, telefono, mensaje, imagen_path=None):
        try:
            # 1. Navegar al chat directo
            mensaje_encoded = urllib.parse.quote(mensaje)
            link = f"https://web.whatsapp.com/send?phone={telefono}&text={mensaje_encoded}"
            self.driver.get(link)

            # 2. Esperar a que cargue la caja de texto o detectar error de número
            try:
                # Verificar si salta alerta de número inválido
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "invalido") or contains(text(), "invalid")]'))
                )
                return "FALLIDO: Número Inválido"
            except:
                pass # Si no hay error, continuamos

            # Esperar a que el chat esté listo (caja de texto presente)
            try:
                caja_texto = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]'))
                )
            except:
                return "FALLIDO: Tiempo de carga excedido"
                
            time.sleep(2) # Pequeña pausa humana

            # 3. Adjuntar Imagen (Si existe)
            if imagen_path:
                try:
                    # Buscar el botón de adjuntar (clip)
                    btn_clip = self.driver.find_element(By.XPATH, '//div[@title="Adjuntar" or @title="Attach"]')
                    btn_clip.click()
                    time.sleep(1)

                    # Buscar el input oculto de tipo file y enviar la ruta
                    input_img = self.driver.find_element(By.XPATH, '//input[@accept="image/*,video/mp4,video/3gpp,video/quicktime"]')
                    input_img.send_keys(os.path.abspath(imagen_path))
                    
                    # Esperar a que cargue la vista previa de la imagen
                    time.sleep(3) 
                    
                    # Buscar botón de enviar (el de la vista previa de imagen es diferente al de texto)
                    btn_enviar_img = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, '//span[@data-icon="send"]'))
                    )
                    btn_enviar_img.click()
                    time.sleep(2) # Esperar a que salga
                except Exception as e:
                    return f"PARCIAL: Texto enviado, Imagen falló ({str(e)})"

            # 4. Enviar Texto (Si no hubo imagen, o para confirmar el texto si va separado)
            # Si enviamos imagen, el texto suele ir como caption. Si no, damos enter al texto.
            if not imagen_path:
                caja_texto.send_keys(Keys.ENTER)
            
            return "ENVIADO"

        except Exception as e:
            return f"ERROR: {str(e)}"

    def cerrar(self):
        if self.driver:
            self.driver.quit()

# --- FUNCIONES AUXILIARES ---
@st.cache_data
def generar_plantilla():
    # Crea un archivo en memoria para descargar
    df_plantilla = pd.DataFrame({
        "nombre": ["Juan Perez", "Maria Gomez"],
        "telefono": ["573001234567", "573109876543"],
        "segmento": ["Lider", "Voluntario"]
    })
    buffer = BytesIO()
    # Guardamos como CSV en el buffer
    df_plantilla.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer

# --- INTERFAZ STREAMLIT ---

st.title("📢 Gestor de Campañas WhatsApp")
st.markdown("""
### Panel de Control de Envíos Masivos
Utiliza esta herramienta para conectar con tu base de datos de ciudadanos.
""")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    st.write("Ajusta los tiempos para simular comportamiento humano y evitar bloqueos.")
    velocidad_min = st.slider("Espera Mínima (seg)", 5, 20, 8)
    velocidad_max = st.slider("Espera Máxima (seg)", 21, 60, 15)
    
    st.divider()
    st.info("💡 **Tip:** Asegúrate de que los teléfonos incluyan el código de país (ej. 57 para Colombia) sin el signo +.")

# --- SECCIÓN 1: GESTIÓN DE DATOS ---
st.header("1. Carga de Base de Datos")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("**¿No tienes el formato?**")
    plantilla_csv = generar_plantilla()
    st.download_button(
        label="📥 Descargar Plantilla Ejemplo",
        data=plantilla_csv,
        file_name="plantilla_contactos.csv",
        mime="text/csv",
        help="Descarga este archivo para ver cómo organizar tus datos."
    )

with col2:
    uploaded_file = st.file_uploader("Adjuntar archivo de contactos", type=['csv', 'xlsx'])

if uploaded_file:
    # Lógica para leer CSV o Excel
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        # Normalizar nombres de columnas (quitar espacios y poner en minuscula)
        df.columns = [c.lower().strip() for c in df.columns]
        
        st.success(f"✅ Archivo cargado correctamente: {len(df)} contactos detectados.")
        
        # Validar columnas necesarias
        col_opciones = df.columns.tolist()
        
        c1, c2 = st.columns(2)
        with c1:
            col_telefono = st.selectbox("Selecciona la columna del TELÉFONO", col_opciones)
        with c2:
            col_nombre = st.selectbox("Selecciona la columna del NOMBRE", col_opciones)

        # Previsualización de datos
        with st.expander("Ver primeros 5 registros"):
            st.dataframe(df.head())

    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")

    st.divider()

    # --- SECCIÓN 2: COMPOSICIÓN ---
    st.header("2. Redacción del Mensaje")
    
    col_msg, col_img = st.columns([2, 1])
    
    with col_msg:
        mensaje_template = st.text_area(
            "Escribe el mensaje", 
            height=150,
            value="Hola {nombre}, queremos invitarte a conocer nuestras propuestas.",
            help="Usa {nombre} para insertar automáticamente el nombre del contacto."
        )
        # Vista previa dinámica
        if not df.empty:
            ejemplo_nombre = df.iloc[0][col_nombre]
            st.info(f"👁️ Vista previa: {mensaje_template.format(nombre=ejemplo_nombre)}")

    with col_img:
        st.write("**Adjuntar Imagen (Opcional)**")
        imagen_file = st.file_uploader("Sube una imagen (JPG/PNG)", type=['png', 'jpg', 'jpeg'])
        ruta_imagen = None
        
        if imagen_file:
            # Guardar temporalmente
            with open("temp_image.png", "wb") as f:
                f.write(imagen_file.getbuffer())
            ruta_imagen = "temp_image.png"
            st.image(imagen_file, width=150, caption="Imagen lista")

    st.divider()

    # --- SECCIÓN 3: EJECUCIÓN ---
    st.header("3. Iniciar Envío Masivo")
    
    st.warning("⚠️ Al iniciar, se abrirá una ventana de Chrome. No la cierres ni la minimices totalmente.")
    
    if st.button("🚀 INICIAR CAMPAÑA AHORA", type="primary"):
        bot = WhatsAppBot()
        st.write("Iniciando motor de WhatsApp...")
        
        if bot.iniciar_driver():
            st.info("👉 Escanea el código QR en la nueva ventana de Chrome.")
            
            # Espera de login
            placeholders = st.empty()
            
            # Intentamos detectar si ya cargó
            waited = 0
            login_success = False
            while waited < 60:
                if bot.esperar_qr():
                    login_success = True
                    break
                time.sleep(1)
                waited += 1
            
            if login_success:
                placeholders.success("¡Conectado! Enviando mensajes...")
                time.sleep(2)
                
                progreso = st.progress(0)
                status_text = st.empty()
                resultados = []
                
                total_envios = len(df)
                
                for index, row in df.iterrows():
                    nombre = str(row[col_nombre])
                    telefono_raw = str(row[col_telefono])
                    # Limpieza básica de teléfono (solo digitos)
                    telefono = ''.join(filter(str.isdigit, telefono_raw))
                    
                    # Personalización
                    try:
                        primer_nombre = nombre.split()[0].title()
                        mensaje_final = mensaje_template.format(nombre=primer_nombre)
                    except:
                        mensaje_final = mensaje_template
                    
                    status_text.text(f"⏳ Enviando {index+1}/{total_envios} a: {nombre}")
                    
                    # Acción de envío
                    estado = bot.enviar_mensaje(telefono, mensaje_final, ruta_imagen)
                    
                    resultados.append({
                        "Nombre": nombre,
                        "Telefono": telefono,
                        "Estado": estado,
                        "Hora": datetime.now().strftime("%H:%M:%S")
                    })
                    
                    progreso.progress((index + 1) / total_envios)
                    
                    # Pausa Anti-Bloqueo
                    if index < total_envios - 1: # No esperar en el último
                        espera = random.uniform(velocidad_min, velocidad_max)
                        time.sleep(espera)
                
                bot.cerrar()
                status_text.text("✅ Proceso completado.")
                
                # Resultados Finales
                df_res = pd.DataFrame(resultados)
                st.subheader("📊 Reporte de Resultados")
                st.dataframe(df_res)
                
                # Botón descarga reporte
                csv_res = df_res.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte Final",
                    data=csv_res,
                    file_name=f'reporte_envios_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                    mime='text/csv',
                )
                
                # Limpieza
                if ruta_imagen and os.path.exists(ruta_imagen):
                    os.remove(ruta_imagen)
            else:
                st.error("No se detectó el inicio de sesión (QR). Intenta de nuevo.")
                bot.cerrar()
        else:
            st.error("Error crítico al abrir el navegador.")

else:
    st.info("👆 Sube un archivo CSV o Excel en la sección 1 para comenzar.")

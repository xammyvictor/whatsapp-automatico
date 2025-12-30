import streamlit as st
import pandas as pd
import time
import random
import os
import urllib.parse
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
            caja_texto = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]'))
            )
            time.sleep(2) # Pequeña pausa humana

            # 3. Adjuntar Imagen (Si existe)
            if imagen_path:
                try:
                    # Buscar el botón de adjuntar (clip)
                    btn_clip = self.driver.find_element(By.XPATH, '//div[@title="Adjuntar" or @title="Attach"]')
                    btn_clip.click()
                    time.sleep(1)

                    # Buscar el input oculto de tipo file y enviar la ruta
                    # Nota: WhatsApp cambia sus XPaths a menudo. Buscamos el input genérico de archivo dentro del menú
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

# --- INTERFAZ STREAMLIT ---

st.title("📢 Gestor de Campañas WhatsApp")
st.markdown("""
Esta herramienta automatiza el envío de mensajes y medios. 
**Nota:** Requiere mantener la ventana de Chrome abierta y el teléfono conectado.
""")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    velocidad_min = st.slider("Espera Mínima (seg)", 5, 20, 10)
    velocidad_max = st.slider("Espera Máxima (seg)", 21, 60, 25)
    
    st.info("💡 Mantén tiempos altos para evitar bloqueos por parte de WhatsApp.")

# Paso 1: Carga de Datos
st.subheader("1. Base de Datos")
uploaded_file = st.file_uploader("Sube tu archivo CSV o Excel", type=['csv', 'xlsx'])

if uploaded_file:
    # Cargar DF
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # Limpieza básica
    df.columns = [c.lower().strip() for c in df.columns] # Normalizar columnas
    
    st.dataframe(df.head())
    
    col_telefono = st.selectbox("Columna de Teléfono", df.columns)
    col_nombre = st.selectbox("Columna de Nombre", df.columns)
    
    # Validar formato
    st.caption(f"Total de registros: {len(df)}")

    # Paso 2: Mensaje
    st.subheader("2. Componer Mensaje")
    mensaje_template = st.text_area(
        "Escribe tu mensaje (Usa {nombre} para personalizar)", 
        height=150,
        value="Hola {nombre}, te compartimos información importante de nuestra gestión."
    )
    
    # Vista previa del mensaje
    if not df.empty:
        ejemplo_nombre = df.iloc[0][col_nombre]
        st.info(f"Vista previa: {mensaje_template.format(nombre=ejemplo_nombre)}")

    # Paso 3: Imagen (Opcional)
    st.subheader("3. Multimedia (Opcional)")
    imagen_file = st.file_uploader("Adjuntar imagen (JPG/PNG)", type=['png', 'jpg', 'jpeg'])
    ruta_imagen = None
    
    if imagen_file:
        # Guardar temporalmente la imagen para que Selenium la pueda leer
        with open(os.path.join("temp_image.png"), "wb") as f:
            f.write(imagen_file.getbuffer())
        ruta_imagen = "temp_image.png"
        st.image(imagen_file, width=200, caption="Imagen a enviar")

    # Paso 4: Ejecución
    st.subheader("4. Ejecutar Campaña")
    
    if st.button("🚀 INICIAR CAMPAÑA", type="primary"):
        bot = WhatsAppBot()
        st.write("Iniciando navegador...")
        
        if bot.iniciar_driver():
            st.warning("⚠️ Por favor escanea el código QR en la ventana que se abrió.")
            
            # Esperar login
            placeholders = st.empty()
            placeholders.info("Esperando escaneo de QR...")
            
            try:
                WebDriverWait(bot.driver, 60).until(
                    EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]'))
                )
                placeholders.success("¡Sesión iniciada! Comenzando envíos...")
                time.sleep(3)
                
                # Barra de progreso
                progreso = st.progress(0)
                status_text = st.empty()
                
                resultados = []
                
                for index, row in df.iterrows():
                    nombre = str(row[col_nombre])
                    # Limpieza agresiva de teléfono
                    telefono = ''.join(filter(str.isdigit, str(row[col_telefono])))
                    
                    # Personalizar
                    try:
                        mensaje_final = mensaje_template.format(nombre=nombre.split()[0].title())
                    except:
                        mensaje_final = mensaje_template # Fallback si falla el format
                    
                    status_text.text(f"Procesando {index+1}/{len(df)}: {nombre}...")
                    
                    # ENVIAR
                    estado = bot.enviar_mensaje(telefono, mensaje_final, ruta_imagen)
                    
                    # Guardar log
                    resultados.append({
                        "Nombre": nombre,
                        "Telefono": telefono,
                        "Estado": estado,
                        "Hora": datetime.now().strftime("%H:%M:%S")
                    })
                    
                    # Actualizar progreso
                    progreso.progress((index + 1) / len(df))
                    
                    # Espera aleatoria (Anti-Ban)
                    tiempo_espera = random.uniform(velocidad_min, velocidad_max)
                    time.sleep(tiempo_espera)
                
                bot.cerrar()
                st.success("✅ Campaña finalizada")
                
                # Mostrar resultados y permitir descarga
                df_res = pd.DataFrame(resultados)
                st.dataframe(df_res)
                
                csv = df_res.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Descargar Reporte de Envío",
                    data=csv,
                    file_name='reporte_envios_whatsapp.csv',
                    mime='text/csv',
                )
                
                # Limpiar imagen temp
                if ruta_imagen and os.path.exists(ruta_imagen):
                    os.remove(ruta_imagen)
                    
            except Exception as e:
                st.error(f"Error durante la ejecución: {e}")
                bot.cerrar()
        else:
            st.error("No se pudo iniciar el navegador Chrome.")

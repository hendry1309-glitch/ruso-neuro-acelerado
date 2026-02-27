import streamlit as st
import sqlite3
import pandas as pd
from gtts import gTTS
import io
import random
import time
from datetime import datetime, timedelta
import requests

# --- ESTILO PARA APP NATIVA (Ocultar menús de sistema y mejorar botones) ---
st.set_page_config(page_title="Ruso Neuro-Acelerado", layout="centered")

st.markdown("""
    <style>
    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Fondo estilo iOS */
    .main { background-color: #F2F2F7; }
    
    /* Botones de Navegación Superior */
    div.stButton > button:first-child {
        border-radius: 10px;
        background-color: white;
        color: #007AFF;
        border: 1px solid #E5E5EA;
        font-weight: 500;
        margin-bottom: 0px;
    }
    
    /* Botones de Acción (Memorizado/No) */
    .action-btn button {
        border-radius: 15px !important;
        height: 4em !important;
    }
    
    .card { 
        background: white; 
        padding: 30px; 
        border-radius: 25px; 
        box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
        text-align: center;
        margin-top: 20px;
    }
    
    /* Botones grandes para iPhone */
    .big-btn button {
        height: 3.5em !important;
        font-size: 18px !important;
        font-weight: 600 !important;
        border-radius: 20px !important;
    }
    
    /* Tarjetas de quiz */
    .quiz-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 40px;
        border-radius: 30px;
        text-align: center;
        margin: 20px 0;
    }
    
    /* Animación de pulsación */
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE BASE DE DATOS MEJORADO ---
def get_db():
    conn = sqlite3.connect('ruso_neuro.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS palacio 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  ruso TEXT, trans TEXT, esp TEXT, mne TEXT, 
                  ubicacion TEXT, estado TEXT DEFAULT 'nuevo',
                  repeticiones INTEGER DEFAULT 0,
                  dificultad REAL DEFAULT 2.5,
                  ultima_repaso TEXT,
                  palace_room TEXT,
                  imagen_url TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS estadisticas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  fecha TEXT,
                  palabras_aprendidas INTEGER,
                  repasadas INTEGER,
                  aciertos INTEGER,
                  fallos INTEGER)''')
    conn.commit()
    return conn

db = get_db()

# --- FUNCIÓN PARA CARGAR DESDE GOOGLE SHEETS ---
def cargar_desde_google_sheets(sheet_url):
    """Carga palabras desde Google Sheets usando URL pública"""
    try:
        # Convertir URL de Google Sheets a formato CSV export
        if 'docs.google.com/spreadsheets' in sheet_url:
            # Extraer el ID del spreadsheet
            import re
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url)
            if match:
                sheet_id = match.group(1)
                # Construir URL de exportación CSV
                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
                
                # Leer el CSV
                df = pd.read_csv(csv_url)
                return df
        return None
    except Exception as e:
        st.error(f"Error al cargar desde Google Sheets: {e}")
        return None

# --- CARGA AUTOMÁTICA DE PALABRAS INICIALES ---
def cargar_palabras_iniciales():
    """Carga palabras desde el CSV si la base de datos está vacía"""
    count = db.execute("SELECT COUNT(*) FROM palacio").fetchone()[0]
    if count == 0:
        try:
            # Leer el CSV manualmente para manejar formato complejo
            import csv
            contador = 0
            
            with open('palabras.csv', 'r', encoding='utf-8') as file:
                csv_reader = csv.reader(file)
                next(csv_reader)  # Saltar encabezado
                
                for row in csv_reader:
                    try:
                        # Saltar filas vacías o inválidas
                        if len(row) < 3 or not row[0] or not row[2]:
                            continue
                            
                        ruso = row[0].strip()
                        trans = row[1].strip() if len(row) > 1 and row[1] else ""
                        esp = row[2].strip()
                        
                        # Verificar que no sean solo espacios o caracteres raros
                        if len(ruso) < 1 or len(esp) < 1:
                            continue
                            
                        # Unir todas las columnas restantes como mnemotecnia
                        mnemotecnia = ""
                        if len(row) > 3:
                            mnemotecnia = " ".join([x.strip() for x in row[3:] if x.strip()])
                        
                        # Si no hay mnemotecnia válida, generar una
                        if not mnemotecnia or mnemotecnia == "":
                            mnemotecnia = generar_mnemotecnia_auto(ruso, esp)
                        
                        ubicacion = generar_ubicacion_palacio(esp)
                        
                        db.execute("""INSERT INTO palacio 
                                     (ruso, trans, esp, mne, ubicacion, palace_room, imagen_url) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                 (ruso, trans, esp, mnemotecnia, ubicacion, ubicacion, get_imagen_contextual(esp)))
                        contador += 1
                        
                        # Mostrar progreso
                        if contador % 100 == 0:
                            print(f"Procesadas {contador} palabras...")
                            
                    except Exception as e:
                        continue
            
            db.commit()
            if contador > 0:
                st.success(f"🎉 Se han cargado automáticamente {contador} palabras desde tu archivo CSV")
            else:
                st.warning("No se encontraron palabras válidas en el archivo CSV")
        except Exception as e:
            st.error(f"Error al cargar el archivo CSV: {e}")
            # Intentar con el otro archivo como respaldo
            try:
                df = pd.read_csv('RUSO.csv')
                contador = 0
                for _, row in df.iterrows():
                    try:
                        if pd.notna(row['ruso']) and pd.notna(row['esp']):
                            ubicacion = generar_ubicacion_palacio(row['esp'])
                            mnemotecnia = row['mne'] if pd.notna(row['mne']) and row['mne'] != '' else generar_mnemotecnia_auto(row['ruso'], row['esp'])
                            
                            db.execute("""INSERT INTO palacio 
                                         (ruso, trans, esp, mne, ubicacion, palace_room, imagen_url) 
                                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                 (row['ruso'], row['trans'], row['esp'], mnemotecnia, ubicacion, ubicacion, get_imagen_contextual(row['esp'])))
                            contador += 1
                    except:
                        continue
                
                db.commit()
                if contador > 0:
                    st.success(f"🎉 Se han cargado {contador} palabras desde el archivo RUSO.csv")
            except Exception as e2:
                st.error(f"No se pudo cargar ningún archivo: {e2}")

# Cargar palabras iniciales
cargar_palabras_iniciales()

# --- FUNCIONES DE MNEMOTECNIA Y PALACIO ---
def generar_ubicacion_palacio(palabra_esp):
    """Genera ubicación en el palacio de la memoria"""
    rooms = [
        "Entrada Principal", "Sala de Estar", "Cocina", "Dormitorio Principal",
        "Baño", "Oficina", "Biblioteca", "Jardín", "Garaje", "Ático",
        "Sótano", "Terraza", "Comedor", "Sala de Música", "Gimnasio"
    ]
    return random.choice(rooms)

def generar_mnemotecnia_auto(ruso, esp):
    """Genera mnemotecnia automática si no existe"""
    return f"Visualiza: {esp} mientras escuchas '{ruso}' en un ambiente ruso"

def get_imagen_contextual(palabra_esp):
    """Obtiene imagen contextual específica optimizada para iOS"""
    
    # URLs optimizadas para iOS (más pequeñas y confiables)
    imagenes_especificas = {
        # Saludos y personas
        "hola": "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg?w=400&h=300&fit=crop",
        "adios": "https://images.pexels.com/photos/762020/pexels-photo-762020.jpeg?w=400&h=300&fit=crop",
        "gracias": "https://images.pexels.com/photos/2690323/pexels-photo-2690323.jpeg?w=400&h=300&fit=crop",
        "por favor": "https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg?w=400&h=300&fit=crop",
        "perdon": "https://images.pexels.com/photos/3184338/pexels-photo-3184338.jpeg?w=400&h=300&fit=crop",
        
        # Lugares
        "casa": "https://images.pexels.com/photos/106399/pexels-photo-106399.jpeg?w=400&h=300&fit=crop",
        "cocina": "https://images.pexels.com/photos/1579739/pexels-photo-1579739.jpeg?w=400&h=300&fit=crop",
        "habitacion": "https://images.pexels.com/photos/1642128/pexels-photo-1642128.jpeg?w=400&h=300&fit=crop",
        "baño": "https://images.pexels.com/photos/269077/pexels-photo-269077.jpeg?w=400&h=300&fit=crop",
        "jardin": "https://images.pexels.com/photos/1402787/pexels-photo-1402787.jpeg?w=400&h=300&fit=crop",
        
        # Comida y bebida
        "agua": "https://images.pexels.com/photos/327090/pexels-photo-327090.jpeg?w=400&h=300&fit=crop",
        "comida": "https://images.pexels.com/photos/704971/pexels-photo-704971.jpeg?w=400&h=300&fit=crop",
        "pan": "https://images.pexels.com/photos/209540/pexels-photo-209540.jpeg?w=400&h=300&fit=crop",
        "cafe": "https://images.pexels.com/photos/312418/pexels-photo-312418.jpeg?w=400&h=300&fit=crop",
        
        # Animales
        "perro": "https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg?w=400&h=300&fit=crop",
        "gato": "https://images.pexels.com/photos/1170989/pexels-photo-1170989.jpeg?w=400&h=300&fit=crop",
        "caballo": "https://images.pexels.com/photos/1996333/pexels-photo-1996333.jpeg?w=400&h=300&fit=crop",
        
        # Naturaleza
        "arbol": "https://images.pexels.com/photos/2690323/pexels-photo-2690323.jpeg?w=400&h=300&fit=crop",
        "flor": "https://images.pexels.com/photos/36764/pexels-photo-36764.jpeg?w=400&h=300&fit=crop",
        "sol": "https://images.pexels.com/photos/1509508/pexels-photo-1509508.jpeg?w=400&h=300&fit=crop",
        "luna": "https://images.pexels.com/photos/186980/pexels-photo-186980.jpeg?w=400&h=300&fit=crop",
        
        # Transporte
        "coche": "https://images.pexels.com/photos/116675/pexels-photo-116675.jpeg?w=400&h=300&fit=crop",
        "avion": "https://images.pexels.com/photos/102986/pexels-photo-102986.jpeg?w=400&h=300&fit=crop",
        "tren": "https://images.pexels.com/photos/50711/pexels-photo-50711.jpeg?w=400&h=300&fit=crop",
        
        # Acciones
        "correr": "https://images.pexels.com/photos/1503921/pexels-photo-1503921.jpeg?w=400&h=300&fit=crop",
        "caminar": "https://images.pexels.com/photos/3821962/pexels-photo-3821962.jpeg?w=400&h=300&fit=crop",
        "comer": "https://images.pexels.com/photos/704971/pexels-photo-704971.jpeg?w=400&h=300&fit=crop",
        "beber": "https://images.pexels.com/photos/3184291/pexels-photo-3184291.jpeg?w=400&h=300&fit=crop",
        "dormir": "https://images.pexels.com/photos/1589329/pexels-photo-1589329.jpeg?w=400&h=300&fit=crop",
        
        # Emociones
        "feliz": "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg?w=400&h=300&fit=crop",
        "triste": "https://images.pexels.com/photos/269077/pexels-photo-269077.jpeg?w=400&h=300&fit=crop",
        "enojado": "https://images.pexels.com/photos/3184338/pexels-photo-3184338.jpeg?w=400&h=300&fit=crop",
    }
    
    # Buscar palabra exacta primero
    palabra_lower = palabra_esp.lower().strip()
    if palabra_lower in imagenes_especificas:
        return imagenes_especificas[palabra_lower]
    
    # Buscar si contiene alguna palabra clave
    for clave, url in imagenes_especificas.items():
        if clave in palabra_lower:
            return url
    
    # Imágenes por categoría optimizadas para iOS
    if any(word in palabra_lower for word in ['persona', 'gente', 'hombre', 'mujer', 'niño']):
        return "https://images.pexels.com/photos/837358/pexels-photo-837358.jpeg?w=400&h=300&fit=crop"
    
    elif any(word in palabra_lower for word in ['comida', 'beber', 'cafe', 'agua', 'pan']):
        return "https://images.pexels.com/photos/704971/pexels-photo-704971.jpeg?w=400&h=300&fit=crop"
    
    elif any(word in palabra_lower for word in ['casa', 'hogar', 'habitacion', 'cocina']):
        return "https://images.pexels.com/photos/106399/pexels-photo-106399.jpeg?w=400&h=300&fit=crop"
    
    elif any(word in palabra_lower for word in ['naturaleza', 'arbol', 'flor', 'sol', 'luna']):
        return "https://images.pexels.com/photos/1509508/pexels-photo-1509508.jpeg?w=400&h=300&fit=crop"
    
    elif any(word in palabra_lower for word in ['animal', 'perro', 'gato', 'pajaro']):
        return "https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg?w=400&h=300&fit=crop"
    
    elif any(word in palabra_lower for word in ['coche', 'carro', 'auto', 'avion', 'tren']):
        return "https://images.pexels.com/photos/116675/pexels-photo-116675.jpeg?w=400&h=300&fit=crop"
    
    # Imagen genérica de aprendizaje optimizada para iOS
    return "https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=400&h=300&fit=crop"

# --- SISTEMA DE REPETICIÓN ESPACIADA ---
def calcular_siguiente_repaso(dificultad, repeticiones):
    """Algoritmo SM-2 modificado para repetición espaciada"""
    if repeticiones == 0:
        return 1  # 1 día
    elif repeticiones == 1:
        return 3  # 3 días
    else:
        # Fórmula SM-2: intervalo = intervalo_anterior * dificultad
        intervalo = (3 * (repeticiones - 1)) * dificultad
        return min(intervalo, 30)  # Máximo 30 días

def actualizar_palabra(palabra_id, estado, acierto=None):
    """Actualiza estado y dificultad de palabra"""
    if acierto is not None:
        # Actualizar dificultad según respuesta
        if acierto:
            nueva_dificultad = max(1.3, db.execute("SELECT dificultad FROM palacio WHERE id = ?", (palabra_id,)).fetchone()[0] * 0.8)
            db.execute("UPDATE palacio SET repeticiones = repeticiones + 1, dificultad = ?, ultima_repaso = ? WHERE id = ?", 
                      (nueva_dificultad, datetime.now().strftime('%Y-%m-%d'), palabra_id))
        else:
            nueva_dificultad = min(3.5, db.execute("SELECT dificultad FROM palacio WHERE id = ?", (palabra_id,)).fetchone()[0] * 1.2)
            db.execute("UPDATE palacio SET dificultad = ?, repeticiones = 0 WHERE id = ?", (nueva_dificultad, palabra_id))
    else:
        db.execute("UPDATE palacio SET estado = ? WHERE id = ?", (estado, palabra_id))
    db.commit()

# --- FUNCIONES DE AUDIO NEURO ---
def generar_audio_subliminal(texto_ruso, significado, mnemotecnia, ubicacion):
    """Genera audio subliminal enfocado en mnemotecnia y ubicación"""
    afirmacion = f"""
    En {ubicacion}, 
    '{texto_ruso}' es '{significado}'. 
    {mnemotecnia}
    """
    tts = gTTS(afirmacion, lang='es', slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    return fp

def get_audio_pronunciacion(texto_ruso):
    """Obtiene audio de pronunciación rusa compatible con iOS"""
    try:
        # Configuración optimizada para iOS
        tts = gTTS(texto_ruso, lang='ru', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)  # Resetear puntero para iOS
        return fp
    except Exception as e:
        st.error(f"Error generando audio: {e}")
        return None

# --- LÓGICA DE NAVEGACIÓN (Simulando App Nativa con Session State) ---
if 'vista' not in st.session_state:
    st.session_state.vista = 'Entrenar'

# BARRA DE NAVEGACIÓN SUPERIOR (BOTONES)
col_nav1, col_nav2, col_nav3, col_nav4, col_nav5 = st.columns(5)
with col_nav1:
    if st.button("🎯", key="nav_entrenar"): st.session_state.vista = 'Entrenar'
with col_nav2:
    if st.button("🔄", key="nav_repaso"): st.session_state.vista = 'Repaso'
with col_nav3:
    if st.button("🏰", key="nav_palacio"): st.session_state.vista = 'Palacio'
with col_nav4:
    if st.button("📥", key="nav_cargar"): st.session_state.vista = 'Cargar'
with col_nav5:
    if st.button("🧠", key="nav_neuro"): st.session_state.vista = 'Neuro'

st.divider()

# --- VISTA: ENTRENAMIENTO ---
if st.session_state.vista == 'Entrenar':
    st.header("🎯 Entrenamiento Neuro-Acelerado")
    
    # Obtener palabras pendientes en orden
    df = pd.read_sql_query("SELECT * FROM palacio WHERE estado != 'memorizado' ORDER BY id ASC", db)
    
    if df.empty:
        st.info("🎉 ¡Felicidades! Has memorizado todas las palabras. Ve a Repaso para consolidar.")
    else:
        # Inicializar índice de palabra actual
        if 'indice_palabra_actual' not in st.session_state:
            st.session_state.indice_palabra_actual = 0
        
        # Asegurar que el índice esté dentro de los límites
        if st.session_state.indice_palabra_actual >= len(df):
            st.session_state.indice_palabra_actual = 0
        elif st.session_state.indice_palabra_actual < 0:
            st.session_state.indice_palabra_actual = len(df) - 1
        
        palabra = df.iloc[st.session_state.indice_palabra_actual]
        
        # Actualizar ubicación si no existe
        if not palabra['ubicacion'] or pd.isna(palabra['ubicacion']):
            ubicacion = generar_ubicacion_palacio(palabra['esp'])
            db.execute("UPDATE palacio SET ubicacion = ?, palace_room = ? WHERE id = ?", 
                      (ubicacion, ubicacion, palabra['id']))
            db.commit()
            palabra['ubicacion'] = ubicacion
        
        # Actualizar mnemotecnia si no existe
        if not palabra['mne'] or pd.isna(palabra['mne']):
            mnemotecnia = generar_mnemotecnia_auto(palabra['ruso'], palabra['esp'])
            db.execute("UPDATE palacio SET mne = ? WHERE id = ?", (mnemotecnia, palabra['id']))
            db.commit()
            palabra['mne'] = mnemotecnia
        
        # Mostrar ubicación en el palacio
        st.markdown(f"🏰 **Sala del Palacio:** {palabra['ubicacion']}")
        
        # TARJETA PRINCIPAL CON PALABRA RUSA
        st.markdown(f"""
            <div class="card pulse">
                <h1 style="font-size: 70px; margin-bottom:10px; color: #FF4B4B;">{palabra['ruso']}</h1>
                <p style="color: #007AFF; font-size: 22px; margin: 0;">{palabra['trans']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # IMAGEN CONTEXTUAL MEJORADA - TIEMPO REAL
        # Generar imagen nueva cada vez para asegurar tiempo real
        imagen_url = get_imagen_contextual(palabra['esp'])
        
        # Forzar recarga de imagen con timestamp único
        timestamp = int(time.time())
        imagen_url_con_timestamp = f"{imagen_url}&t={timestamp}"
        
        # Contenedor para imagen con contexto
        st.markdown(f"""
        <div style="background: white; padding: 20px; border-radius: 15px; margin: 20px 0; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="color: #007AFF; margin-bottom: 15px;">🖼️ Contexto Visual</h3>
            <p style="color: #666; font-size: 14px; margin-bottom: 10px;">Asocia esta imagen con: <strong>{palabra['esp']}</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Mostrar imagen optimizada para iOS
        try:
            st.image(imagen_url_con_timestamp, use_container_width=True, caption=f"🇷🇺 {palabra['ruso']} - {palabra['esp']}", output_format="JPEG")
        except Exception as e:
            st.error("Error cargando imagen")
            st.image("https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=400&h=300&fit=crop", use_container_width=True, caption="🇷🇺 Imagen de respaldo")
        
        # Instrucción visual
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #FF6B6B, #FFE66D); color: white; padding: 15px; border-radius: 10px; margin: 10px 0; text-align: center;">
            <strong>👁️ Visualiza:</strong> Mira la imagen y repite "{palabra['ruso']}" mientras piensas en "{palabra['esp']}"
        </div>
        """, unsafe_allow_html=True)
        
        # SECCIÓN DE AUDIO
        col_audio1, col_audio2, col_audio3 = st.columns(3)
        with col_audio1:
            if st.button("🔊 PRONUNCIACIÓN", key="audio_normal", use_container_width=True):
                audio = get_audio_pronunciacion(palabra['ruso'])
                if audio:
                    st.audio(audio, format='audio/mp3', autoplay=True)
                else:
                    st.error("No se pudo generar el audio")
        
        with col_audio2:
            if st.button("🧠 AUDIO SUBLIMINAL", key="audio_subliminal", use_container_width=True):
                audio = generar_audio_subliminal(palabra['ruso'], palabra['esp'], palabra['mne'], palabra['ubicacion'])
                if audio:
                    st.audio(audio, format='audio/mp3', autoplay=True)
                    st.info(f"💫 Audio subliminal activado - Conectando '{palabra['ruso']}' con {palabra['ubicacion']}")
                else:
                    st.error("No se pudo generar el audio subliminal")
        
        with col_audio3:
            if st.button("🎵 RITMO", key="audio_ritmo", use_container_width=True):
                # Audio rítmico para memorización
                try:
                    tts = gTTS(f"{palabra['ruso']}. {palabra['esp']}. {palabra['ruso']}.", lang='ru', slow=True)
                    fp = io.BytesIO()
                    tts.write_to_fp(fp)
                    fp.seek(0)
                    st.audio(fp, format='audio/mp3', autoplay=True)
                except Exception as e:
                    st.error("Error generando audio rítmico")
        
        st.divider()
        
        # SECCIÓN DE NAVEGACIÓN Y EDICIÓN
        col_nav1, col_nav2, col_nav3, col_nav4, col_nav5 = st.columns(5)
        
        with col_nav1:
            if st.button("⬅️ Anterior", key="btn_anterior", use_container_width=True):
                if st.session_state.indice_palabra_actual > 0:
                    st.session_state.indice_palabra_actual -= 1
                st.session_state.revelado = False
                st.rerun()
        
        with col_nav2:
            if st.button("✏️ Editar", key="btn_editar", use_container_width=True):
                st.session_state.editar_palabra = palabra['id']
                st.rerun()
        
        with col_nav3:
            st.info(f"📍 {st.session_state.indice_palabra_actual + 1}/{len(df)}")
        
        with col_nav4:
            if st.button("➡️ Siguiente", key="btn_siguiente", use_container_width=True):
                if st.session_state.indice_palabra_actual < len(df) - 1:
                    st.session_state.indice_palabra_actual += 1
                st.session_state.revelado = False
                st.rerun()
        
        with col_nav5:
            if st.button("🔀 Aleatorio", key="btn_aleatorio", use_container_width=True):
                st.session_state.indice_palabra_actual = random.randint(0, len(df) - 1)
                st.session_state.revelado = False
                st.rerun()
        
        # SECCIÓN DE EDICIÓN
        if st.session_state.get('editar_palabra') == palabra['id']:
            st.subheader("✏️ Editar Palabra")
            
            with st.form(f"edit_form_{palabra['id']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    nuevo_ruso = st.text_input("🇷🇺 Palabra en Ruso", value=palabra['ruso'])
                    nuevo_trans = st.text_input("🔤 Transliteración", value=palabra['trans'])
                
                with col2:
                    nuevo_esp = st.text_input("🇪🇸 Significado", value=palabra['esp'])
                    nueva_mne = st.text_area("🧠 Mnemotecnia", value=palabra['mne'], height=100)
                
                nueva_ubicacion = st.selectbox("🏰 Ubicación en el Palacio", 
                    ["Entrada Principal", "Sala de Estar", "Cocina", "Dormitorio Principal",
                     "Baño", "Oficina", "Biblioteca", "Jardín", "Garaje", "Ático",
                     "Sótano", "Terraza", "Comedor", "Sala de Música", "Gimnasio"],
                    index=["Entrada Principal", "Sala de Estar", "Cocina", "Dormitorio Principal",
                           "Baño", "Oficina", "Biblioteca", "Jardín", "Garaje", "Ático",
                           "Sótano", "Terraza", "Comedor", "Sala de Música", "Gimnasio"].index(palabra['ubicacion']) if palabra['ubicacion'] in ["Entrada Principal", "Sala de Estar", "Cocina", "Dormitorio Principal", "Baño", "Oficina", "Biblioteca", "Jardín", "Garaje", "Ático", "Sótano", "Terraza", "Comedor", "Sala de Música", "Gimnasio"] else 0)
                
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                        db.execute("""UPDATE palacio SET 
                                     ruso = ?, trans = ?, esp = ?, mne = ?, 
                                     ubicacion = ?, palace_room = ? WHERE id = ?""",
                                 (nuevo_ruso, nuevo_trans, nuevo_esp, nueva_mne, 
                                  nueva_ubicacion, nueva_ubicacion, palabra['id']))
                        db.commit()
                        st.success("✅ Palabra actualizada!")
                        st.session_state.editar_palabra = None
                        # Actualizar palabra actual
                        df_actualizado = pd.read_sql_query("SELECT * FROM palacio WHERE id = ?", db, params=(palabra['id'],))
                        if not df_actualizado.empty:
                            # Actualizar la palabra en el dataframe
                            for i, row in df.iterrows():
                                if row['id'] == palabra['id']:
                                    df.iloc[i] = df_actualizado.iloc[0]
                                    palabra = df_actualizado.iloc[0]
                                    break
                        time.sleep(1)
                        st.rerun()
                
                with col_cancel:
                    if st.form_submit_button("❌ Cancelar"):
                        st.session_state.editar_palabra = None
                        st.rerun()
        
        st.divider()
        
        # SECCIÓN DE REVELACIÓN
        if not st.session_state.get('revelado', False):
            if st.button("💡 REVELAR SIGNIFICADO Y MNEMOTECNIA", key="revelar", use_container_width=True, type="primary"):
                st.session_state.revelado = True
                st.rerun()
        else:
            # Mostrar información revelada
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"""
                    <div class="card" style="background: linear-gradient(135deg, #4CAF50, #45a049); color: white;">
                        <h3>✅ Significado</h3>
                        <h2>{palabra['esp']}</h2>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                    <div class="card" style="background: linear-gradient(135deg, #FF9800, #F57C00); color: white;">
                        <h3>🧠 Mnemotecnia</h3>
                        <p>{palabra['mne']}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Botones de acción
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("✅ MEMORIZADO", key="btn_memorizado", use_container_width=True, type="primary"):
                    actualizar_palabra(palabra['id'], 'memorizado')
                    st.session_state.revelado = False
                    st.success("🎉 ¡Palabra memorizada!")
                    time.sleep(1)
                    st.rerun()
            
            with col_btn2:
                if st.button("❌ NO MEMORIZADO", key="btn_no_memorizado", use_container_width=True):
                    st.session_state.revelado = False
                    st.rerun()
            
            with col_btn3:
                if st.button("🔄 REPETIR MÁS TARDE", key="btn_repetir", use_container_width=True):
                    actualizar_palabra(palabra['id'], 'nuevo')
                    st.session_state.revelado = False
                    st.rerun()

# --- VISTA: REPASO (QUIZ 4 OPCIONES) ---
elif st.session_state.vista == 'Repaso':
    st.header("🔄 Repaso Inteligente")
    
    # Obtener palabras memorizadas para repaso
    df_memorizadas = pd.read_sql_query("SELECT * FROM palacio WHERE estado = 'memorizado' ORDER BY id ASC", db)
    
    # Debug: mostrar cuántas palabras memorizadas hay
    if not df_memorizadas.empty:
        st.info(f"📚 Tienes {len(df_memorizadas)} palabras memorizadas para repasar")
    else:
        # También buscar palabras con otros estados por si acaso
        df_todas = pd.read_sql_query("SELECT * FROM palacio ORDER BY id ASC", db)
        st.warning(f"📊 Total de palabras en base de datos: {len(df_todas)}")
        
        if not df_todas.empty:
            # Mostrar estados disponibles
            estados = df_todas['estado'].unique() if 'estado' in df_todas.columns else []
            st.write(f"Estados encontrados: {estados}")
            
            # Si hay palabras pero ninguna marcada como memorizada, mostrar todas para repaso
            df_memorizadas = df_todas
            st.info("🔄 Mostrando todas las palabras para repaso")
    
    if df_memorizadas.empty:
        st.info("📚 No hay palabras memorizadas para repasar. Empieza con el entrenamiento 🎯")
    else:
        # Inicializar quiz si no existe
        if 'quiz_actual' not in st.session_state:
            st.session_state.quiz_actual = None
            st.session_state.quiz_opciones = []
            st.session_state.quiz_respuesta_correcta = None
        
        # Seleccionar palabra aleatoria para quiz
        if st.session_state.quiz_actual is None:
            palabra_quiz = df_memorizadas.iloc[0]
            st.session_state.quiz_actual = palabra_quiz
            
            # Determinar dirección del quiz (aleatorio)
            direccion = random.choice(['ru->es', 'es->ru'])
            
            if direccion == 'ru->es':
                # Mostrar ruso, opciones en español
                pregunta = palabra_quiz['ruso']
                respuesta_correcta = palabra_quiz['esp']
                
                # Generar opciones incorrectas
                otras_palabras = df_memorizadas[df_memorizadas['id'] != palabra_quiz['id']]['esp'].tolist()
                opciones_incorrectas = random.sample(otras_palabras, min(3, len(otras_palabras)))
                opciones = [respuesta_correcta] + opciones_incorrectas
                random.shuffle(opciones)
                
                st.session_state.quiz_pregunta = f"🇷🇺 ¿Qué significa '{pregunta}'?"
                st.session_state.quiz_opciones = opciones
                st.session_state.quiz_respuesta_correcta = respuesta_correcta
                st.session_state.quiz_tipo = 'ru->es'
                
            else:
                # Mostrar español, opciones en ruso
                pregunta = palabra_quiz['esp']
                respuesta_correcta = palabra_quiz['ruso']
                
                # Generar opciones incorrectas
                otras_palabras = df_memorizadas[df_memorizadas['id'] != palabra_quiz['id']]['ruso'].tolist()
                opciones_incorrectas = random.sample(otras_palabras, min(3, len(otras_palabras)))
                opciones = [respuesta_correcta] + opciones_incorrectas
                random.shuffle(opciones)
                
                st.session_state.quiz_pregunta = f"🇪🇸 ¿Cómo se dice '{pregunta}' en ruso?"
                st.session_state.quiz_opciones = opciones
                st.session_state.quiz_respuesta_correcta = respuesta_correcta
                st.session_state.quiz_tipo = 'es->ru'
        
        # Mostrar quiz
        st.markdown(f"""
            <div class="quiz-card">
                <h2>{st.session_state.quiz_pregunta}</h2>
            </div>
            """, unsafe_allow_html=True)
        
        # Mostrar opciones
        for i, opcion in enumerate(st.session_state.quiz_opciones):
            if st.button(f"📍 {opcion}", key=f"opcion_{i}", use_container_width=True):
                if opcion == st.session_state.quiz_respuesta_correcta:
                    st.success("🎉 ¡Correcto! ¡Bien hecho!")
                    actualizar_palabra(st.session_state.quiz_actual['id'], 'memorizado', acierto=True)
                else:
                    st.error(f"❌ Incorrecto. La respuesta correcta era: {st.session_state.quiz_respuesta_correcta}")
                    actualizar_palabra(st.session_state.quiz_actual['id'], 'memorizado', acierto=False)
                
                # Resetear quiz
                st.session_state.quiz_actual = None
                time.sleep(2)
                st.rerun()
        
        # Botón para saltar pregunta
        if st.button("⏭️ Siguiente Pregunta", use_container_width=True):
            st.session_state.quiz_actual = None
            st.rerun()

# --- VISTA: PALACIO (GESTIÓN MNEMOTÉCNICA) ---
elif st.session_state.vista == 'Palacio':
    st.header("🏰 Palacio de la Memoria")
    
    # Estadísticas del palacio
    total_palabras = db.execute("SELECT COUNT(*) FROM palacio").fetchone()[0]
    memorizadas = db.execute("SELECT COUNT(*) FROM palacio WHERE estado = 'memorizado'").fetchone()[0]
    pendientes = total_palabras - memorizadas
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 Total Palabras", total_palabras)
    with col2:
        st.metric("✅ Memorizadas", memorizadas)
    with col3:
        st.metric("⏳ Pendientes", pendientes)
    
    st.divider()
    
    # Editor del palacio
    df_all = pd.read_sql_query("SELECT id, ruso, trans, esp, mne, ubicacion, estado FROM palacio", db)
    
    if not df_all.empty:
        st.subheader("📝 Editar Mnemotécnicas y Ubicaciones")
        edited = st.data_editor(df_all, hide_index=True, use_container_width=True)
        
        if st.button("💾 Guardar Cambios", use_container_width=True, type="primary"):
            # Actualizar base de datos con cambios
            for _, row in edited.iterrows():
                db.execute("""UPDATE palacio SET 
                             ruso = ?, trans = ?, esp = ?, mne = ?, 
                             ubicacion = ?, estado = ? WHERE id = ?""",
                         (row['ruso'], row['trans'], row['esp'], row['mne'], 
                          row['ubicacion'], row['estado'], row['id']))
            db.commit()
            st.success("✅ Palacio actualizado correctamente!")
            time.sleep(1)
            st.rerun()
    else:
        st.info("📭 El palacio está vacío. Carga palabras para empezar.")

# --- VISTA: CARGAR DATOS ---
elif st.session_state.vista == 'Cargar':
    st.header("📥 Cargar Diccionario")
    
    tab1, tab2, tab3 = st.tabs(["📁 Subir Archivo", "📝 Ingreso Manual", "📊 Google Sheets"])
    
    with tab1:
        st.subheader("Subir Archivo CSV")
        
        # Botón de emergencia para cargar palabras
        if st.button("🚨 Cargar Palabras de Emergencia", type="primary"):
            st.info("Intentando cargar palabras desde archivos locales...")
            cargar_palabras_iniciales()
            count = db.execute("SELECT COUNT(*) FROM palacio").fetchone()[0]
            if count > 0:
                st.success(f"✅ Se cargaron {count} palabras correctamente!")
                st.rerun()
            else:
                st.error("❌ No se pudieron cargar las palabras")
        
        archivo = st.file_uploader("Selecciona tu archivo CSV", type=['csv'])
        
        if archivo:
            try:
                df_nuevo = pd.read_csv(archivo)
                st.success(f"📊 Archivo cargado: {len(df_nuevo)} filas")
                st.dataframe(df_nuevo.head())
                
                # Mapeo de columnas
                st.subheader("🔗 Mapear Columnas")
                columnas_df = df_nuevo.columns.tolist()
                
                col_map = {}
                col_map['ruso'] = st.selectbox("Columna Ruso:", columnas_df, index=0 if 'ruso' in columnas_df else 0)
                col_map['trans'] = st.selectbox("Columna Transliteración:", columnas_df, index=1 if 'trans' in columnas_df or 'transliteracion' in columnas_df else 1)
                col_map['esp'] = st.selectbox("Columna Español:", columnas_df, index=2 if 'esp' in columnas_df or 'español' in columnas_df else 2)
                col_map['mne'] = st.selectbox("Columna Mnemotecnia:", columnas_df, index=3 if 'mne' in columnas_df or 'mnemotecnia' in columnas_df else 3)
                
                if st.button("🚀 Procesar y Cargar", type="primary"):
                    contador = 0
                    for _, row in df_nuevo.iterrows():
                        try:
                            ubicacion = generar_ubicacion_palacio(row[col_map['esp']])
                            mnemotecnia = row[col_map['mne']] if pd.notna(row[col_map['mne']]) else generar_mnemotecnia_auto(row[col_map['ruso']], row[col_map['esp']])
                            
                            db.execute("""INSERT INTO palacio 
                                         (ruso, trans, esp, mne, ubicacion, palace_room, imagen_url) 
                                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                     (row[col_map['ruso']], row[col_map['trans']], row[col_map['esp']], 
                                      mnemotecnia, ubicacion, ubicacion, get_imagen_contextual(row[col_map['esp']])))
                            contador += 1
                        except Exception as e:
                            st.warning(f"Error en fila: {e}")
                    
                    db.commit()
                    st.success(f"🎉 ¡Se han cargado {contador} palabras al palacio!")
                    time.sleep(2)
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error al leer archivo: {e}")
    
    with tab2:
        st.subheader("Agregar Palabra Manualmente")
        
        with st.form("form_manual"):
            col1, col2 = st.columns(2)
            
            with col1:
                ruso_input = st.text_input("🇷🇺 Palabra en Ruso")
                trans_input = st.text_input("🔤 Transliteración")
            
            with col2:
                esp_input = st.text_input("🇪🇸 Significado en Español")
                mne_input = st.text_area("🧠 Mnemotecnia", height=100)
            
            if st.form_submit_button("➕ Agregar Palabra", type="primary"):
                if ruso_input and esp_input:
                    ubicacion = generar_ubicacion_palacio(esp_input)
                    mnemotecnia = mne_input if mne_input else generar_mnemotecnia_auto(ruso_input, esp_input)
                    
                    db.execute("""INSERT INTO palacio 
                                 (ruso, trans, esp, mne, ubicacion, palace_room, imagen_url) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
                             (ruso_input, trans_input, esp_input, mnemotecnia, 
                              ubicacion, ubicacion, get_imagen_contextual(esp_input)))
                    db.commit()
                    st.success("✅ Palabra agregada correctamente!")
                    st.rerun()
    
    with tab3:
        st.subheader("📊 Cargar desde Google Sheets")
        
        # URL predefinida del usuario
        default_url = "https://docs.google.com/spreadsheets/d/1F0MMq0PW3AsIrSntrSZnhvGsqm91_YZbIrBkSkTwrsc/edit?gid=1713246625#gid=1713246625"
        
        sheet_url = st.text_input("🔗 URL de Google Sheets", value=default_url, help="Pega la URL de tu Google Sheet aquí")
        
        col_info, col_load = st.columns([2, 1])
        with col_info:
            st.info("💡 El Google Sheet debe estar configurado como 'Público en la web' para poder acceder")
        
        with col_load:
            if st.button("📥 Cargar desde Google Sheets", type="primary"):
                if sheet_url:
                    with st.spinner("🔄 Cargando palabras desde Google Sheets..."):
                        df_google = cargar_desde_google_sheets(sheet_url)
                        
                        if df_google is not None:
                            st.success(f"📊 Se cargaron {len(df_google)} filas desde Google Sheets")
                            st.dataframe(df_google.head())
                            
                            # Procesar similar al CSV
                            contador = 0
                            for _, row in df_google.iterrows():
                                try:
                                    # Adaptar columnas (pueden tener diferentes nombres)
                                    ruso = row.get('ruso', row.get('Ruso', ''))
                                    trans = row.get('trans', row.get('transliteracion', row.get('Transliteracion', '')))
                                    esp = row.get('esp', row.get('español', row.get('Español', '')))
                                    mne = row.get('mne', row.get('mnemotecnia', row.get('Mnemotecnia', '')))
                                    
                                    if ruso and esp:
                                        ubicacion = generar_ubicacion_palacio(esp)
                                        mnemotecnia = mne if mne else generar_mnemotecnia_auto(ruso, esp)
                                        
                                        # Verificar si ya existe para evitar duplicados
                                        existe = db.execute("SELECT id FROM palacio WHERE ruso = ? AND esp = ?", (ruso, esp)).fetchone()
                                        if not existe:
                                            db.execute("""INSERT INTO palacio 
                                                         (ruso, trans, esp, mne, ubicacion, palace_room, imagen_url) 
                                                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                                     (ruso, trans, esp, mnemotecnia, ubicacion, ubicacion, get_imagen_contextual(esp)))
                                            contador += 1
                                except Exception as e:
                                    continue
                            
                            db.commit()
                            st.success(f"🎉 Se agregaron {contador} palabras nuevas desde Google Sheets!")
                            
                            if contador > 0:
                                # Reiniciar índice de entrenamiento
                                if 'indice_palabra_actual' in st.session_state:
                                    del st.session_state.indice_palabra_actual
                                st.rerun()
                        else:
                            st.error("❌ No se pudieron cargar los datos. Verifica que el Google Sheet sea público")
                else:
                    st.error("❌ Por favor, ingresa una URL válida de Google Sheets")
        
        # Instrucciones
        with st.expander("📖 ¿Cómo configurar Google Sheets?"):
            st.markdown("""
            ### Pasos para configurar tu Google Sheet:
            
            1. **Abre tu Google Sheet**
            2. **Ve a Compartir** (botón右上角)
            3. **Configura el acceso**: 
               - En "Acceso general", selecciona "Cualquier persona con el enlace"
               - En la lista desplegable, selecciona "Lector"
            4. **Copia la URL** y pégala aquí
            5. **Asegúrate de que las columnas sean**:
               - `ruso` o `Ruso`
               - `trans` o `transliteracion` 
               - `esp` o `español`
               - `mne` o `mnemotecnia` (opcional)
            
            ### Formato recomendado:
            | ruso | trans | esp | mne |
            |------|-------|-----|-----|
            | привет | priviet | hola | un jet privado |
            | дом | dom | casa | un domo |
            """)

# --- VISTA: NEURO-PROGRAMACIÓN ---
elif st.session_state.vista == 'Neuro':
    st.header("🧠 Neuro-Programación")
    
    st.markdown("""
    <div class="card">
        <h2>🧬 Técnicas de Reprogramación Inconsciente</h2>
        <p>Estas técnicas están diseñadas para acelerar tu aprendizaje a nivel subconsciente.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Estadísticas de progreso
    st.subheader("📊 Tu Progreso")
    
    total = db.execute("SELECT COUNT(*) FROM palacio").fetchone()[0]
    memorizadas = db.execute("SELECT COUNT(*) FROM palacio WHERE estado = 'memorizado'").fetchone()[0]
    progreso = (memorizadas / total * 100) if total > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 Total", total)
    with col2:
        st.metric("✅ Dominadas", memorizadas)
    with col3:
        st.metric("📈 Progreso", f"{progreso:.1f}%")
    
    # Barra de progreso
    st.progress(progreso / 100)
    
    st.divider()
    
    # Sesión de programación inconsciente
    st.subheader("🎯 Sesión de Programación")
    
    # Obtener palabras para programación
    df_programacion = pd.read_sql_query("SELECT * FROM palacio ORDER BY id ASC LIMIT 5", db)
    
    if not df_programacion.empty:
        st.info("🎧 Ponte auriculares y relájate. Esta sesión programará tu inconsciente.")
        
        for _, palabra in df_programacion.iterrows():
            with st.expander(f"🧠 {palabra['ruso']} - {palabra['esp']}", expanded=False):
                # Mostrar imagen contextual primero con timestamp para tiempo real
                imagen_url = get_imagen_contextual(palabra['esp'])
                timestamp = int(time.time())
                imagen_url_con_timestamp = f"{imagen_url}&t={timestamp}"
                # Mostrar imagen optimizada para iOS
                try:
                    st.image(imagen_url_con_timestamp, use_container_width=True, caption=f"🖼️ {palabra['esp']}", output_format="JPEG")
                except Exception as e:
                    st.error("Error cargando imagen")
                    st.image("https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=400&h=300&fit=crop", use_container_width=True, caption="🖼️ Imagen de respaldo")
                
                st.write(f"**🏰 Ubicación:** {palabra['ubicacion']}")
                st.write(f"**💭 Mnemotecnia:** {palabra['mne']}")
                
                # Audio de programación mejorado
                if st.button(f"🎵 Programar '{palabra['ruso']}'", key=f"programar_{palabra['id']}"):
                    # Audio subliminal completo con conexión palacio-mnemotecnia
                    audio_subliminal = generar_audio_subliminal(palabra['ruso'], palabra['esp'], palabra['mne'], palabra['ubicacion'])
                    if audio_subliminal:
                        st.audio(audio_subliminal, format='audio/mp3', autoplay=True)
                        st.success(f"🧠 Programación activa: {palabra['ubicacion']} ↔ {palabra['ruso']} ↔ {palabra['esp']}")
                        
                        # Audio de pronunciación rusa
                        audio_ruso = get_audio_pronunciacion(palabra['ruso'])
                        if audio_ruso:
                            st.audio(audio_ruso, format='audio/mp3', autoplay=True)
                    else:
                        st.error("Error generando audio de programación")
                    
                    # Visualización de la conexión
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                color: white; padding: 15px; border-radius: 10px; margin: 10px 0;">
                        <strong>🧠 Conexión Neural:</strong><br>
                        🏰 {palabra['ubicacion']} → 🇷🇺 {palabra['ruso']} → 🇪🇸 {palabra['esp']}<br>
                        💭 {palabra['mne']}
                    </div>
                    """, unsafe_allow_html=True)
    
    # Técnicas de visualización
    st.subheader("👁️ Técnicas de Visualización")
    
    with st.expander("🏰 Técnica del Palacio Mental"):
        st.write("""
        1. **Cierra los ojos** y respira profundamente
        2. **Visualiza tu palacio** con todos sus detalles
        3. **Ubica cada palabra** en su sala correspondiente
        4. **Camina mentalmente** por el palacio visitando cada palabra
        5. **Repite en voz alta** mientras visualizas
        """)
    
    with st.expander("🌊 Técnica de Onda Alpha"):
        st.write("""
        1. **Encuentra un lugar tranquilo**
        2. **Escucha música relajante** (432 Hz recomendado)
        3. **Repite las palabras** en estado de relajación
        4. **Visualiza escenas** donde usas las palabras
        5. **Siente la emoción** de hablar ruso fluidamente
        """)
    
    # Configuración de sesión
    st.subheader("⚙️ Configuración de Sesión")
    
    session_duration = st.slider("⏱️ Duración de sesión (minutos):", 5, 60, 15)
    words_per_session = st.slider("📝 Palabras por sesión:", 1, 20, 5)
    
    if st.button("🚀 Iniciar Sesión Neuro", type="primary"):
        st.success(f"🎯 Sesión iniciada: {words_per_session} palabras por {session_duration} minutos")
        st.info("💡 Recuerda: La consistencia es más importante que la intensidad")
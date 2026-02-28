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
    """Obtiene imagen contextual usando búsqueda de Google optimizada para acciones y verbos"""
    
    # Palabras clave para acciones/verbos (prioridad alta)
    acciones_verbos = {
        # Verbos de movimiento
        "correr": "https://source.unsplash.com/400x300/?running,person,action",
        "caminar": "https://source.unsplash.com/400x300/?walking,person,street", 
        "saltar": "https://source.unsplash.com/400x300/?jumping,action,sport",
        "nadar": "https://source.unsplash.com/400x300/?swimming,pool,water",
        "volar": "https://source.unsplash.com/400x300/?flying,plane,sky",
        "conducir": "https://source.unsplash.com/400x300/?driving,car,road",
        "bailar": "https://source.unsplash.com/400x300/?dancing,people,music",
        "cantar": "https://source.unsplash.com/400x300/?singing,microphone,performance",
        
        # Verbos de comunicación
        "hablar": "https://source.unsplash.com/400x300/?speaking,people,conversation",
        "escuchar": "https://source.unsplash.com/400x300/?listening,ear,person",
        "leer": "https://source.unsplash.com/400x300/?reading,book,person",
        "escribir": "https://source.unsplash.com/400x300/?writing,pen,desk",
        "llamar": "https://source.unsplash.com/400x300/?calling,phone,communication",
        
        # Verbos de alimentación
        "comer": "https://source.unsplash.com/400x300/?eating,food,meal",
        "beber": "https://source.unsplash.com/400x300/?drinking,water,beverage",
        "cocinar": "https://source.unsplash.com/400x300/?cooking,kitchen,food",
        
        # Verbos diarios
        "trabajar": "https://source.unsplash.com/400x300/?working,office,computer",
        "estudiar": "https://source.unsplash.com/400x300/?studying,books,learning",
        "dormir": "https://source.unsplash.com/400x300/?sleeping,bed,rest",
        "despertar": "https://source.unsplash.com/400x300/?waking,morning,sunlight",
        "duchar": "https://source.unsplash.com/400x300/?showering,bathroom,water",
        "vestir": "https://source.unsplash.com/400x300/?dressing,clothes,fashion",
        
        # Verbos sociales
        "amar": "https://source.unsplash.com/400x300/?love,couple,heart",
        "ayudar": "https://source.unsplash.com/400x300/?helping,people,support",
        "jugar": "https://source.unsplash.com/400x300/?playing,game,fun",
        "reir": "https://source.unsplash.com/400x300/?laughing,people,happy",
        "llorar": "https://source.unsplash.com/400x300/?crying,tears,sad",
        
        # Verbos de creación
        "crear": "https://source.unsplash.com/400x300/?creating,art,hands",
        "construir": "https://source.unsplash.com/400x300/?building,construction,tools",
        "pintar": "https://source.unsplash.com/400x300/?painting,art,canvas",
        "dibujar": "https://source.unsplash.com/400x300/?drawing,pencil,paper",
        
        # Saludos y expresiones
        "hola": "https://source.unsplash.com/400x300/?hello,waving,greeting",
        "adios": "https://source.unsplash.com/400x300/?goodbye,waving,farewell",
        "gracias": "https://source.unsplash.com/400x300/?thank,gratitude,appreciation",
        "por favor": "https://source.unsplash.com/400x300/?please,polite,request",
        "perdon": "https://source.unsplash.com/400x300/?sorry,apology,forgiveness",
    }
    
    # Objetos y lugares (prioridad media)
    objetos_lugares = {
        # Lugares
        "casa": "https://source.unsplash.com/400x300/?house,home,building",
        "cocina": "https://source.unsplash.com/400x300/?kitchen,cooking,food",
        "habitacion": "https://source.unsplash.com/400x300/?bedroom,sleep,rest",
        "baño": "https://source.unsplash.com/400x300/?bathroom,hygiene,clean",
        "jardin": "https://source.unsplash.com/400x300/?garden,flowers,nature",
        "escuela": "https://source.unsplash.com/400x300/?school,education,learning",
        "hospital": "https://source.unsplash.com/400x300/?hospital,medical,health",
        "tienda": "https://source.unsplash.com/400x300/?shop,store,shopping",
        
        # Comida y bebida
        "agua": "https://source.unsplash.com/400x300/?water,drink,hydration",
        "comida": "https://source.unsplash.com/400x300/?food,meal,delicious",
        "pan": "https://source.unsplash.com/400x300/?bread,bakery,fresh",
        "cafe": "https://source.unsplash.com/400x300/?coffee,drink,morning",
        "leche": "https://source.unsplash.com/400x300/?milk,drink,white",
        
        # Animales
        "perro": "https://source.unsplash.com/400x300/?dog,pet,animal",
        "gato": "https://source.unsplash.com/400x300/?cat,pet,feline",
        "caballo": "https://source.unsplash.com/400x300/?horse,animal,riding",
        "pajaro": "https://source.unsplash.com/400x300/?bird,flying,sky",
        
        # Naturaleza
        "arbol": "https://source.unsplash.com/400x300/?tree,nature,forest",
        "flor": "https://source.unsplash.com/400x300/?flower,garden,beauty",
        "sol": "https://source.unsplash.com/400x300/?sun,light,sky",
        "luna": "https://source.unsplash.com/400x300/?moon,night,stars",
        "mar": "https://source.unsplash.com/400x300/?ocean,water,waves",
        "montaña": "https://source.unsplash.com/400x300/?mountain,nature,landscape",
        
        # Transporte
        "coche": "https://source.unsplash.com/400x300/?car,vehicle,road",
        "avion": "https://source.unsplash.com/400x300/?airplane,flying,travel",
        "tren": "https://source.unsplash.com/400x300/?train,railway,transport",
        "bicicleta": "https://source.unsplash.com/400x300/?bicycle,cycling,sport",
        
        # Personas y familia
        "hombre": "https://source.unsplash.com/400x300/?man,person,male",
        "mujer": "https://source.unsplash.com/400x300/?woman,person,female",
        "niño": "https://source.unsplash.com/400x300/?child,kid,playing",
        "familia": "https://source.unsplash.com/400x300/?family,people,together",
        "amigo": "https://source.unsplash.com/400x300/?friends,people,happy",
        
        # Emociones
        "feliz": "https://source.unsplash.com/400x300/?happy,joy,smiling",
        "triste": "https://source.unsplash.com/400x300/?sad,crying,emotion",
        "enojado": "https://source.unsplash.com/400x300/?angry,emotion,frustrated",
        "contento": "https://source.unsplash.com/400x300/?content,happy,peaceful",
    }
    
    # Buscar palabra exacta primero en acciones/verbos
    palabra_lower = palabra_esp.lower().strip()
    if palabra_lower in acciones_verbos:
        return acciones_verbos[palabra_lower]
    
    # Buscar palabra exacta en objetos/lugares
    if palabra_lower in objetos_lugares:
        return objetos_lugares[palabra_lower]
    
    # Buscar si contiene alguna palabra clave de acciones/verbos
    for clave, url in acciones_verbos.items():
        if clave in palabra_lower:
            return url
    
    # Buscar si contiene alguna palabra clave de objetos/lugares
    for clave, url in objetos_lugares.items():
        if clave in palabra_lower:
            return url
    
    # Búsqueda por categorías con Google Images
    if any(word in palabra_lower for word in ['correr', 'caminar', 'mover', 'viajar']):
        return "https://source.unsplash.com/400x300/?action,movement,people"
    
    elif any(word in palabra_lower for word in ['comer', 'beber', 'alimento', 'bebida']):
        return "https://source.unsplash.com/400x300/?food,drink,meal"
    
    elif any(word in palabra_lower for word in ['casa', 'hogar', 'habitacion', 'lugar']):
        return "https://source.unsplash.com/400x300/?home,house,interior"
    
    elif any(word in palabra_lower for word in ['naturaleza', 'arbol', 'flor', 'paisaje']):
        return "https://source.unsplash.com/400x300/?nature,landscape,outdoor"
    
    elif any(word in palabra_lower for word in ['animal', 'perro', 'gato', 'mascota']):
        return "https://source.unsplash.com/400x300/?animal,pet,wildlife"
    
    elif any(word in palabra_lower for word in ['coche', 'carro', 'auto', 'transporte']):
        return "https://source.unsplash.com/400x300/?vehicle,transport,road"
    
    elif any(word in palabra_lower for word in ['persona', 'gente', 'hombre', 'mujer']):
        return "https://source.unsplash.com/400x300/?people,person,human"
    
    # Búsqueda genérica con la palabra en español e inglés
    termino_busqueda = palabra_lower.replace(' ', ',')
    return f"https://source.unsplash.com/400x300/?{termino_busqueda},concept,visual"

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
    try:
        if acierto is not None:
            # Obtener dificultad actual con manejo de NULL
            resultado = db.execute("SELECT dificultad FROM palacio WHERE id = ?", (palabra_id,)).fetchone()
            dificultad_actual = resultado[0] if resultado and resultado[0] is not None else 2.5  # Valor por defecto
            
            # Actualizar dificultad según respuesta
            if acierto:
                nueva_dificultad = max(1.3, dificultad_actual * 0.8)
                db.execute("UPDATE palacio SET estado = ?, repeticiones = repeticiones + 1, dificultad = ?, ultima_repaso = ? WHERE id = ?", 
                          (estado, nueva_dificultad, datetime.now().strftime('%Y-%m-%d'), palabra_id))
            else:
                nueva_dificultad = min(3.5, dificultad_actual * 1.2)
                db.execute("UPDATE palacio SET estado = ?, dificultad = ?, repeticiones = 0 WHERE id = ?", (estado, nueva_dificultad, palabra_id))
        else:
            db.execute("UPDATE palacio SET estado = ? WHERE id = ?", (estado, palabra_id))
        
        db.commit()
        return True
    except Exception as e:
        st.error(f"Error actualizando palabra: {e}")
        return False

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

# --- SISTEMA DE DIAGNÓSTICO PARA iOS ---
def mostrar_diagnostico():
    """Mostrar información de diagnóstico para problemas de audio/imagen"""
    with st.expander("🔧 Diagnóstico Técnico", expanded=False):
        st.markdown("### 📊 Información del Sistema")
        
        # Información del navegador
        st.markdown("**Navegador:**")
        st.code(f"User Agent: {st.session_state.get('user_agent', 'No detectado')}")
        
        # Estado de audio
        st.markdown("**Estado del Audio:**")
        if hasattr(st.session_state, 'audio_generado'):
            st.code(f"Audio generado: {st.session_state.audio_generado}")
            st.code(f"Última palabra: {st.session_state.get('ultima_palabra_audio', 'N/A')}")
        else:
            st.code("Audio no inicializado")
        
        # Estado de imágenes
        st.markdown("**Estado de Imágenes:**")
        st.code("Sistema de imágenes: Pexels optimizado")
        st.code("Tamaño: 400x300px")
        st.code("Formato: JPEG")
        
        # Botones de prueba
        st.markdown("**Pruebas Rápidas:**")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🧪 Probar Audio", key="test_audio"):
                try:
                    test_audio = get_audio_pronunciacion("тест")
                    if test_audio:
                        st.audio(test_audio, format='audio/mp3')
                        st.success("✅ Audio funciona")
                    else:
                        st.error("❌ Audio falló")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        
        with col2:
            if st.button("🧪 Probar Imagen", key="test_image"):
                try:
                    test_url = "https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=400&h=300&fit=crop"
                    st.image(test_url, caption="Imagen de prueba")
                    st.success("✅ Imagen funciona")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        
        # Recomendaciones
        st.markdown("**Recomendaciones para iOS:**")
        st.markdown("""
        - 📱 Usa **Safari** (no Chrome/Firefox)
        - 🔊 Asegúrate de que el **silencio** esté desactivado
        - 📶 Conexión **WiFi estable** para imágenes
        - 🔄 **Recarga la página** si hay problemas
        - 📂 **Limpia caché** si persisten los errores
        """)

# --- LÓGICA DE NAVEGACIÓN (Simulando App Nativa con Session State) ---
if 'vista' not in st.session_state:
    st.session_state.vista = 'Entrenar'

# Guardar user agent para diagnóstico
if 'user_agent' not in st.session_state:
    st.session_state.user_agent = "iOS Safari (detectado)"

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
    
    # Mostrar diagnóstico
    mostrar_diagnostico()
    
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
        
        # TARJETA PRINCIPAL CON PALABRA RUSA Y SIGNIFICADO
        st.markdown(f"""
            <div class="card pulse">
                <h1 style="font-size: 70px; margin-bottom:10px; color: #FF4B4B;">{palabra['ruso']}</h1>
                <p style="color: #007AFF; font-size: 22px; margin: 5px 0;">{palabra['trans']}</p>
                <p style="color: #34C759; font-size: 24px; margin: 5px 0; font-weight: bold;">{palabra['esp']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # SIN IMAGEN CONTEXTUAL - MEJOR RENDIMIENTO EN IPHONE
        # Eliminado para mejorar rendimiento y sonido
        
        # SIN IMAGEN - MEJOR RENDIMIENTO PARA IPHONE
        # Imágenes eliminadas para priorizar audio y rendimiento
        
        # SECCIÓN DE AUDIO - SOLUCIÓN DEFINITIVA PARA IPHONE
        st.markdown("---")
        st.markdown("### 🔊 Audio de Aprendizaje")
        
        # Generar audio en tiempo real para iPhone
        try:
            # Audio de pronunciación rusa
            st.markdown("**🇷🇺 Pronunciación Rusa:**")
            audio_ruso = get_audio_pronunciacion(palabra['ruso'])
            if audio_ruso:
                audio_ruso.seek(0)
                st.audio(audio_ruso, format='audio/mp3', autoplay=False)
                st.success("✅ Audio ruso listo")
            else:
                st.error("❌ Error generando audio ruso")
            
            # Audio subliminal
            st.markdown("**🧠 Programación Subliminal:**")
            audio_subliminal = generar_audio_subliminal(palabra['ruso'], palabra['esp'], palabra['mne'], palabra['ubicacion'])
            if audio_subliminal:
                audio_subliminal.seek(0)
                st.audio(audio_subliminal, format='audio/mp3', autoplay=False)
                st.success("✅ Audio subliminal listo")
            else:
                st.error("❌ Error generando audio subliminal")
                
        except Exception as e:
            st.error(f"❌ Error en sistema de audio: {str(e)}")
            st.info("💡 Recarga la página o usa Safari en iPhone")
        
        # INSTRUCCIONES PARA IPHONE
        st.markdown("---")
        st.markdown("### 📱 Instrucciones para iPhone:")
        st.markdown("""
        - 🔊 **Usa Safari** (no Chrome/Firefox)
        - 📱 **Activa el sonido** y quita silencio
        - 🎧 **Usa auriculares** para mejor experiencia
        - 📶 **WiFi estable** para audio sin interrupciones
        - 🔄 **Recarga página** si no hay sonido
        """)
        
        # BOTONES DE AUDIO SIMPLIFICADOS PARA IPHONE
        col_audio1, col_audio2 = st.columns(2)
        
        with col_audio1:
            if st.button("🔊 ESCUCHAR RUSO", key="btn_pronunciacion_simple", use_container_width=True, type="primary"):
                try:
                    audio = get_audio_pronunciacion(palabra['ruso'])
                    if audio:
                        audio.seek(0)
                        st.audio(audio, format='audio/mp3', autoplay=True)
                        st.success("✅ Reproduciendo pronunciación")
                    else:
                        st.error("❌ Error generando audio")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        with col_audio2:
            if st.button("🧠 PROGRAMAR", key="btn_subliminal_simple", use_container_width=True):
                try:
                    audio = generar_audio_subliminal(palabra['ruso'], palabra['esp'], palabra['mne'], palabra['ubicacion'])
                    if audio:
                        audio.seek(0)
                        st.audio(audio, format='audio/mp3', autoplay=True)
                        st.info(f"🧠 Programando: {palabra['ruso']} ↔ {palabra['esp']}")
                    else:
                        st.error("❌ Error generando programación")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        # SIN AUTOPLAY - MEJOR PARA IPHONE
        # El usuario debe hacer clic manualmente para reproducir audio
        
        st.divider()
        
        # SECCIÓN DE NAVEGACIÓN PRINCIPAL
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
        
        # SECCIÓN DE BOTONES DE MEMORIZACIÓN
        st.markdown("---")
        st.markdown("### 🎯 Estado de Memorización")
        
        col_mem1, col_mem2, col_mem3 = st.columns(3)
        
        with col_mem1:
            if st.button("✅ MEMORIZADO", key="btn_memorizado", use_container_width=True, type="primary"):
                actualizar_palabra(palabra['id'], 'memorizado')
                st.session_state.revelado = False
                st.success("🎉 ¡Palabra memorizada!")
                time.sleep(1)
                # Avanzar automáticamente
                if st.session_state.indice_palabra_actual < len(df) - 1:
                    st.session_state.indice_palabra_actual += 1
                st.rerun()
        
        with col_mem2:
            if st.button("❌ NO MEMORIZADO", key="btn_no_memorizado", use_container_width=True):
                actualizar_palabra(palabra['id'], 'pendiente')
                st.session_state.revelado = False
                st.warning("📝 Palabra marcada como no memorizada")
                time.sleep(1)
                # Avanzar automáticamente
                if st.session_state.indice_palabra_actual < len(df) - 1:
                    st.session_state.indice_palabra_actual += 1
                st.rerun()
        
        with col_mem3:
            if st.button("⏰ REPETIR MÁS TARDE", key="btn_repetir", use_container_width=True):
                actualizar_palabra(palabra['id'], 'repasar')
                st.session_state.revelado = False
                st.info("⏰ Palabra programada para repasar más tarde")
                time.sleep(1)
                # Avanzar automáticamente
                if st.session_state.indice_palabra_actual < len(df) - 1:
                    st.session_state.indice_palabra_actual += 1
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
            
            # Estos botones ya están implementados arriba en la sección de memorización
# No se duplican para evitar errores de clave

# --- VISTA: REPASO INTELIGENTE MEJORADO ---
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
        # MODO DE REPASO MEJORADO
        st.markdown("---")
        st.markdown("### 🎯 Modo de Repaso")
        
        modo_repaso = st.radio("Elige el modo de repaso:", 
                              ["📝 Lista Completa", "🎮 Quiz Rápido", "🧠 Repaso Intensivo"],
                              key="modo_repaso")
        
        if modo_repaso == "📝 Lista Completa":
            # MOSTRAR TODAS LAS PALABRAS MEMORIZADAS
            st.markdown("#### 📚 Todas tus palabras memorizadas:")
            
            # Buscador
            termino_busqueda = st.text_input("🔍 Buscar palabra:", key="buscar_repaso")
            
            # Filtrar palabras
            if termino_busqueda:
                df_filtradas = df_memorizadas[
                    df_memorizadas['ruso'].str.contains(termino_busqueda, case=False) |
                    df_memorizadas['esp'].str.contains(termino_busqueda, case=False)
                ]
            else:
                df_filtradas = df_memorizadas
            
            # Mostrar palabras en tarjetas
            for i, (_, palabra) in enumerate(df_filtradas.iterrows()):
                with st.expander(f"🇷🇺 {palabra['ruso']} - 🇪🇸 {palabra['esp']}", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Transliteración:** {palabra['trans']}")
                        st.write(f"**Ubicación:** {palabra['ubicacion']}")
                        st.write(f"**Mnemotecnia:** {palabra['mne']}")
                        
                        # Audio de pronunciación
                        if st.button(f"🔊 Escuchar {palabra['ruso']}", key=f"audio_repaso_{palabra['id']}"):
                            audio = get_audio_pronunciacion(palabra['ruso'])
                            if audio:
                                st.audio(audio, format='audio/mp3', autoplay=True)
                    
                    with col2:
                        # Mostrar imagen contextual
                        imagen_url = get_imagen_contextual(palabra['esp'])
                        timestamp = int(time.time())
                        imagen_url_con_timestamp = f"{imagen_url}&t={timestamp}"
                        
                        try:
                            st.image(imagen_url_con_timestamp, use_container_width=True, caption=f"🖼️ {palabra['esp']}", output_format="JPEG")
                        except:
                            st.warning("⚠️ Imagen no disponible")
                    
                    # Botones de acción
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
                        if st.button("✅ Dominada", key=f"dominada_{palabra['id']}", use_container_width=True):
                            actualizar_palabra(palabra['id'], 'memorizado', acierto=True)
                            st.success("✅ Palabra reforzada")
                            st.rerun()
                    
                    with col_btn2:
                        if st.button("🔄 Repasar", key=f"repaso_individual_{palabra['id']}", use_container_width=True):
                            actualizar_palabra(palabra['id'], 'repasar')
                            st.info("🔄 Programada para repaso")
                            st.rerun()
                    
                    with col_btn3:
                        if st.button("❌ Olvidada", key=f"olvidada_{palabra['id']}", use_container_width=True):
                            actualizar_palabra(palabra['id'], 'pendiente')
                            st.warning("❌ Palabra regresada a pendiente")
                            st.rerun()
        
        elif modo_repaso == "🎮 Quiz Rápido":
            # QUIZ TRADICIONAL MEJORADO
            st.markdown("#### 🎮 Quiz Rápido de 4 Opciones")
            
            # Inicializar quiz si no existe
            if 'quiz_actual' not in st.session_state:
                st.session_state.quiz_actual = None
                st.session_state.quiz_opciones = []
                st.session_state.quiz_respuesta_correcta = None
                st.session_state.puntuacion = 0
                st.session_state.total_preguntas = 0
            
            # Seleccionar palabra aleatoria para quiz
            if st.session_state.quiz_actual is None:
                palabra_quiz = df_memorizadas.sample(1).iloc[0]
                st.session_state.quiz_actual = palabra_quiz
                
                # Determinar dirección del quiz (aleatorio)
                direccion = random.choice(['ru->es', 'es->ru'])
                
                if direccion == 'ru->es':
                    # Mostrar ruso, opciones en español
                    pregunta = palabra_quiz['ruso']
                    respuesta_correcta = palabra_quiz['esp']
                    
                    # Generar opciones incorrectas
                    otras_palabras = df_memorizadas[df_memorizadas['esp'] != respuesta_correcta]
                    if len(otras_palabras) >= 3:
                        opciones_incorrectas = otras_palabras['esp'].sample(3).tolist()
                    else:
                        opciones_incorrectas = otras_palabras['esp'].tolist()
                    
                    st.session_state.quiz_opciones = [respuesta_correcta] + opciones_incorrectas
                    random.shuffle(st.session_state.quiz_opciones)
                    st.session_state.quiz_respuesta_correcta = respuesta_correcta
                    st.session_state.quiz_direccion = 'ru->es'
                    
                else:
                    # Mostrar español, opciones en ruso
                    pregunta = palabra_quiz['esp']
                    respuesta_correcta = palabra_quiz['ruso']
                    
                    # Generar opciones incorrectas
                    otras_palabras = df_memorizadas[df_memorizadas['ruso'] != respuesta_correcta]
                    if len(otras_palabras) >= 3:
                        opciones_incorrectas = otras_palabras['ruso'].sample(3).tolist()
                    else:
                        opciones_incorrectas = otras_palabras['ruso'].tolist()
                    
                    st.session_state.quiz_opciones = [respuesta_correcta] + opciones_incorrectas
                    random.shuffle(st.session_state.quiz_opciones)
                    st.session_state.quiz_respuesta_correcta = respuesta_correcta
                    st.session_state.quiz_direccion = 'es->ru'
            
            # Mostrar quiz actual
            if st.session_state.quiz_actual is not None:
                # Mostrar puntuación
                st.markdown(f"**Puntuación:** {st.session_state.puntuacion}/{st.session_state.total_preguntas}")
                
                st.markdown("---")
                
                # Mostrar pregunta
                if st.session_state.quiz_direccion == 'ru->es':
                    st.markdown(f"#### 🇷🇺 ¿Qué significa: **{st.session_state.quiz_actual['ruso']}**?")
                else:
                    st.markdown(f"#### 🇪🇸 ¿Cómo se dice en ruso: **{st.session_state.quiz_actual['esp']}**?")
                
                # Mostrar opciones
                col1, col2 = st.columns(2)
                for i, opcion in enumerate(st.session_state.quiz_opciones):
                    if i < 2:
                        with col1:
                            if st.button(f"📍 {opcion}", key=f"opcion_{i}", use_container_width=True):
                                st.session_state.total_preguntas += 1
                                if opcion == st.session_state.quiz_respuesta_correcta:
                                    st.success("🎉 ¡Correcto! ¡Bien hecho!")
                                    st.session_state.puntuacion += 1
                                    actualizar_palabra(st.session_state.quiz_actual['id'], 'memorizado', acierto=True)
                                else:
                                    st.error(f"❌ Incorrecto. La respuesta correcta era: {st.session_state.quiz_respuesta_correcta}")
                                    actualizar_palabra(st.session_state.quiz_actual['id'], 'memorizado', acierto=False)
                                
                                # Resetear quiz
                                st.session_state.quiz_actual = None
                                st.session_state.quiz_opciones = []
                                st.session_state.quiz_respuesta_correcta = None
                                time.sleep(2)
                                st.rerun()
                    else:
                        with col2:
                            if st.button(f"📍 {opcion}", key=f"opcion_{i}", use_container_width=True):
                                st.session_state.total_preguntas += 1
                                if opcion == st.session_state.quiz_respuesta_correcta:
                                    st.success("🎉 ¡Correcto! ¡Bien hecho!")
                                    st.session_state.puntuacion += 1
                                    actualizar_palabra(st.session_state.quiz_actual['id'], 'memorizado', acierto=True)
                                else:
                                    st.error(f"❌ Incorrecto. La respuesta correcta era: {st.session_state.quiz_respuesta_correcta}")
                                    actualizar_palabra(st.session_state.quiz_actual['id'], 'memorizado', acierto=False)
                                
                                # Resetear quiz
                                st.session_state.quiz_actual = None
                                st.session_state.quiz_opciones = []
                                st.session_state.quiz_respuesta_correcta = None
                                time.sleep(2)
                                st.rerun()
                
                # Botón para saltar pregunta
                if st.button("⏭️ Saltar pregunta", key="skip_question"):
                    st.session_state.quiz_actual = None
                    st.session_state.quiz_opciones = []
                    st.session_state.quiz_respuesta_correcta = None
                    st.rerun()
        
        else:  # 🧠 Repaso Intensivo
            st.markdown("#### 🧠 Repaso Intensivo - Todas las palabras seguidas")
            
            # Inicializar repaso intensivo
            if 'repaso_intensivo_indice' not in st.session_state:
                st.session_state.repaso_intensivo_indice = 0
                st.session_state.repaso_intensivo_errores = 0
            
            if st.session_state.repaso_intensivo_indice < len(df_memorizadas):
                palabra_actual = df_memorizadas.iloc[st.session_state.repaso_intensivo_indice]
                
                st.markdown(f"**Palabra {st.session_state.repaso_intensivo_indice + 1} de {len(df_memorizadas)}**")
                st.markdown(f"**Errores:** {st.session_state.repaso_intensivo_errores}")
                
                st.markdown("---")
                st.markdown(f"#### 🇷🇺 ¿Qué significa: **{palabra_actual['ruso']}**?")
                
                # Input para respuesta
                respuesta_usuario = st.text_input("Escribe tu respuesta:", key="respuesta_intensiva")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("✅ Comprobar", key="comprobar_intensivo", use_container_width=True):
                        if respuesta_usuario.lower().strip() == palabra_actual['esp'].lower().strip():
                            st.success("🎉 ¡Correcto!")
                            actualizar_palabra(palabra_actual['id'], 'memorizado', acierto=True)
                            st.session_state.repaso_intensivo_indice += 1
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ Incorrecto. La respuesta correcta es: {palabra_actual['esp']}")
                            st.session_state.repaso_intensivo_errores += 1
                            actualizar_palabra(palabra_actual['id'], 'memorizado', acierto=False)
                            time.sleep(2)
                            st.rerun()
                
                with col2:
                    if st.button("🔊 Escuchar", key="escuchar_intensivo", use_container_width=True):
                        audio = get_audio_pronunciacion(palabra_actual['ruso'])
                        if audio:
                            st.audio(audio, format='audio/mp3', autoplay=True)
                
                with col3:
                    if st.button("⏭️ Saltar", key="saltar_intensivo", use_container_width=True):
                        st.session_state.repaso_intensivo_indice += 1
                        st.rerun()
                
                # Mostrar ayuda
                with st.expander("💡 Ayuda", expanded=False):
                    st.write(f"**Mnemotecnia:** {palabra_actual['mne']}")
                    st.write(f"**Ubicación:** {palabra_actual['ubicacion']}")
                    st.write(f"**Transliteración:** {palabra_actual['trans']}")
            
            else:
                st.success("🎉 ¡Has completado el repaso intensivo!")
                st.markdown(f"**Total de errores:** {st.session_state.repaso_intensivo_errores}")
                
                if st.button("🔄 Reiniciar repaso intensivo", key="reiniciar_intensivo"):
                    st.session_state.repaso_intensivo_indice = 0
                    st.session_state.repaso_intensivo_errores = 0
                    st.rerun()

# --- VISTA: PALACIO (GESTIÓN MNEMOTÉCNICA) ---
elif st.session_state.vista == 'Palacio':
    st.header("🏰 Palacio de la Memoria")
    
    # Estadísticas del palacio - CORREGIDO
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

# --- VISTA: NEURO-PROGRAMACIÓN MEJORADA ---
elif st.session_state.vista == 'Neuro':
    st.header("🧠 Neuro-Programación Avanzada")
    
    st.markdown("""
    <div class="card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
        <h2>🧬 Técnicas de Reprogramación Inconsciente</h2>
        <p>Accede a tu potencial máximo con técnicas neuro-científicas probadas</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Estadísticas de progreso mejoradas
    st.subheader("📊 Tu Progreso Neuro-Lingüístico")
    
    total = db.execute("SELECT COUNT(*) FROM palacio").fetchone()[0]
    memorizadas = db.execute("SELECT COUNT(*) FROM palacio WHERE estado = 'memorizado'").fetchone()[0]
    repaso = db.execute("SELECT COUNT(*) FROM palacio WHERE estado = 'repasar'").fetchone()[0]
    progreso = (memorizadas / total * 100) if total > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 Total", total)
    with col2:
        st.metric("✅ Dominadas", memorizadas)
    with col3:
        st.metric("� Repaso", repaso)
    with col4:
        st.metric("�� Progreso", f"{progreso:.1f}%")
    
    # Barra de progreso con colores
    st.progress(progreso / 100)
    
    # Nivel de maestría
    if progreso >= 80:
        st.success("🏆 ¡Nivel EXPERTO! Dominas el ruso avanzado")
    elif progreso >= 60:
        st.info("🎯 Nivel INTERMEDIO - Buen progreso")
    elif progreso >= 40:
        st.warning("📚 Nivel PRINCIPIANTE - Sigue adelante")
    else:
        st.error("🌱 Nivel NOVATO - Empieza tu viaje")
    
    st.divider()
    
    # SECCIÓN DE PROGRAMACIÓN MEJORADA
    st.subheader("🎯 Sesiones de Programación")
    
    # Obtener palabras para programación
    df_programacion = pd.read_sql_query("SELECT * FROM palacio ORDER BY id ASC LIMIT 10", db)
    
    if not df_programacion.empty:
        st.info("🎧 Ponte auriculares y relájate. Esta sesión programará tu inconsciente.")
        
        # Modo de programación
        modo_programacion = st.radio("Elige el modo de programación:", 
                                    ["🎯 Individual", "🌊 Secuencial", "🚀 Intensiva"],
                                    key="modo_programacion")
        
        if modo_programacion == "🎯 Individual":
            # Programación individual mejorada
            st.markdown("#### 🎯 Programación Individual")
            
            palabra_seleccionada = st.selectbox(
                "Selecciona una palabra para programar:",
                options=df_programacion['esp'].tolist(),
                format_func=lambda x: f"🇷🇺 {df_programacion[df_programacion['esp'] == x]['ruso'].iloc[0]} - 🇪🇸 {x}"
            )
            
            palabra = df_programacion[df_programacion['esp'] == palabra_seleccionada].iloc[0]
            
            # Mostrar información completa
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"""
                <div style="background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <h3>🇷🇺 {palabra['ruso']}</h3>
                    <p><strong>Transliteración:</strong> {palabra['trans']}</p>
                    <p><strong>Significado:</strong> {palabra['esp']}</p>
                    <p><strong>Ubicación:</strong> {palabra['ubicacion']}</p>
                    <p><strong>Mnemotecnia:</strong> {palabra['mne']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # Imagen contextual
                imagen_url = get_imagen_contextual(palabra['esp'])
                timestamp = int(time.time())
                imagen_url_con_timestamp = f"{imagen_url}&t={timestamp}"
                
                try:
                    st.image(imagen_url_con_timestamp, use_container_width=True, caption=f"🖼️ {palabra['esp']}", output_format="JPEG")
                except:
                    st.warning("⚠️ Imagen no disponible")
            
            # Controles de programación
            st.markdown("#### 🎛️ Controles de Programación")
            
            col_prog1, col_prog2, col_prog3 = st.columns(3)
            
            with col_prog1:
                if st.button(f"🧠 Programar '{palabra['ruso']}'", key=f"programar_individual_{palabra['id']}", use_container_width=True, type="primary"):
                    # Audio subliminal completo
                    audio_subliminal = generar_audio_subliminal(palabra['ruso'], palabra['esp'], palabra['mne'], palabra['ubicacion'])
                    if audio_subliminal:
                        st.audio(audio_subliminal, format='audio/mp3', autoplay=True)
                        st.success(f"🧠 Programación activa: {palabra['ubicacion']} ↔ {palabra['ruso']} ↔ {palabra['esp']}")
                        
                        # Audio de pronunciación
                        audio_ruso = get_audio_pronunciacion(palabra['ruso'])
                        if audio_ruso:
                            st.audio(audio_ruso, format='audio/mp3', autoplay=True)
                    else:
                        st.error("❌ Error generando programación")
            
            with col_prog2:
                if st.button(f"🔊 Pronunciación", key=f"pronunciacion_individual_{palabra['id']}", use_container_width=True):
                    audio_ruso = get_audio_pronunciacion(palabra['ruso'])
                    if audio_ruso:
                        st.audio(audio_ruso, format='audio/mp3', autoplay=True)
                        st.success("🔊 Escuchando pronunciación rusa")
            
            with col_prog3:
                if st.button(f"💫 Reforzar", key=f"reforzar_individual_{palabra['id']}", use_container_width=True):
                    # Doble programación
                    audio_subliminal = generar_audio_subliminal(palabra['ruso'], palabra['esp'], palabra['mne'], palabra['ubicacion'])
                    if audio_subliminal:
                        st.audio(audio_subliminal, format='audio/mp3', autoplay=True)
                        st.success("💫 Refuerzo triple activado")
                        time.sleep(2)
                        st.audio(audio_subliminal, format='audio/mp3', autoplay=True)
        
        elif modo_programacion == "🌊 Secuencial":
            # Programación secuencial
            st.markdown("#### 🌊 Programación Secuencial")
            st.info("🔄 Las palabras se programarán automáticamente una tras otra")
            
            if 'programacion_secuencial_indice' not in st.session_state:
                st.session_state.programacion_secuencial_indice = 0
            
            if st.session_state.programacion_secuencial_indice < len(df_programacion):
                palabra_actual = df_programacion.iloc[st.session_state.programacion_secuencial_indice]
                
                st.markdown(f"**Programando palabra {st.session_state.programacion_secuencial_indice + 1} de {len(df_programacion)}**")
                st.markdown(f"#### 🇷🇺 {palabra_actual['ruso']} - 🇪🇸 {palabra_actual['esp']}")
                
                # Mostrar imagen
                imagen_url = get_imagen_contextual(palabra_actual['esp'])
                timestamp = int(time.time())
                imagen_url_con_timestamp = f"{imagen_url}&t={timestamp}"
                
                try:
                    st.image(imagen_url_con_timestamp, use_container_width=True, caption=f"🖼️ {palabra_actual['esp']}", output_format="JPEG")
                except:
                    st.warning("⚠️ Imagen no disponible")
                
                # Programación automática
                if st.button("🚀 Iniciar Programación Secuencial", key="iniciar_secuencial", use_container_width=True, type="primary"):
                    # Programar palabra actual
                    audio_subliminal = generar_audio_subliminal(palabra_actual['ruso'], palabra_actual['esp'], palabra_actual['mne'], palabra_actual['ubicacion'])
                    if audio_subliminal:
                        st.audio(audio_subliminal, format='audio/mp3', autoplay=True)
                        
                        # Avanzar automáticamente después de 5 segundos
                        time.sleep(5)
                        st.session_state.programacion_secuencial_indice += 1
                        st.rerun()
                
                # Controles manuales
                col_sec1, col_sec2 = st.columns(2)
                
                with col_sec1:
                    if st.button("⏭️ Siguiente", key="siguiente_secuencial", use_container_width=True):
                        st.session_state.programacion_secuencial_indice += 1
                        st.rerun()
                
                with col_sec2:
                    if st.button("🔄 Reiniciar", key="reiniciar_secuencial", use_container_width=True):
                        st.session_state.programacion_secuencial_indice = 0
                        st.rerun()
            else:
                st.success("🎉 ¡Programación secuencial completada!")
                if st.button("🔄 Reiniciar programación", key="reiniciar_programacion"):
                    st.session_state.programacion_secuencial_indice = 0
                    st.rerun()
        
        else:  # 🚀 Intensiva
            # Programación intensiva
            st.markdown("#### 🚀 Programación Intensiva")
            st.warning("⚡ Modo intensivo - Todas las palabras seguidas")
            
            if st.button("🚀 INICIAR PROGRAMACIÓN INTENSIVA", key="iniciar_intensiva", use_container_width=True, type="primary"):
                st.info("🧠 Iniciando programación intensiva de todas las palabras...")
                
                # Programar todas las palabras seguidas
                for i, (_, palabra) in enumerate(df_programacion.iterrows()):
                    st.markdown(f"**{i+1}/{len(df_programacion)}** - 🇷🇺 {palabra['ruso']} - 🇪🇸 {palabra['esp']}")
                    
                    # Audio subliminal
                    audio_subliminal = generar_audio_subliminal(palabra['ruso'], palabra['esp'], palabra['mne'], palabra['ubicacion'])
                    if audio_subliminal:
                        st.audio(audio_subliminal, format='audio/mp3', autoplay=True)
                        time.sleep(3)  # Pausa entre palabras
                
                st.success("🎉 ¡Programación intensiva completada!")
    
    else:
        st.warning("⚠️ No hay palabras disponibles para programación. Carga algunas palabras primero.")
    
    # SECCIÓN DE TÉCNICAS AVANZADAS
    st.divider()
    st.subheader("🧬 Técnicas Avanzadas")
    
    col_tec1, col_tec2 = st.columns(2)
    
    with col_tec1:
        st.markdown("""
        <div class="card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white;">
            <h3>🎯 Visualización Guiada</h3>
            <p>Cierra los ojos y visualiza cada palabra en su ubicación del palacio mientras escuchas el audio.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_tec2:
        st.markdown("""
        <div class="card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white;">
            <h3>🌊 Ondas Alpha</h3>
            <p>Escucha en estado relajado para máxima absorción subconsciente.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Recomendaciones personalizadas
    st.markdown("---")
    st.subheader("💡 Recomendaciones Personalizadas")
    
    if progreso < 30:
        st.info("🌱 **Recomendación:** Empieza con programación individual para construir bases sólidas")
    elif progreso < 60:
        st.info("🎯 **Recomendación:** Usa programación secuencial para consolidar tu aprendizaje")
    else:
        st.info("🚀 **Recomendación:** Programa intensiva para dominio avanzado")
    
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
                # Mostrar imagen optimizada para iOS - SOLUCIÓN DEFINITIVA
                try:
                    # Verificar que la URL sea válida
                    if imagen_url_con_timestamp and imagen_url_con_timestamp.startswith('http'):
                        st.image(imagen_url_con_timestamp, use_container_width=True, caption=f"🖼️ {palabra['esp']}", output_format="JPEG")
                    else:
                        raise ValueError("URL de imagen inválida")
                        
                except Exception as e:
                    # Imágenes de respaldo para Neuro
                    backup_images = [
                        "https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg?w=400&h=300&fit=crop",
                        "https://images.pexels.com/photos/1108571/pexels-photo-1108571.jpeg?w=400&h=300&fit=crop"
                    ]
                    
                    # Intentar con imágenes de respaldo
                    imagen_cargada = False
                    for backup_url in backup_images:
                        try:
                            st.image(backup_url, use_container_width=True, caption=f"🖼️ {palabra['esp']} (respaldo)", output_format="JPEG")
                            imagen_cargada = True
                            break
                        except:
                            continue
                    
                    if not imagen_cargada:
                        st.warning("⚠️ Imagen no disponible en modo Neuro")
                
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
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
        
        # --- AUDIO CORREGIDO PARA IPHONE (SISTEMA SIMPLE) ---
        st.markdown("---")
        
        # Generar audio simple como en el código base
        try:
            tts = gTTS(palabra['ruso'], lang='ru')
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_bytes = audio_fp.getvalue()
            
            # Botón de reproducción simple
            if st.button("🔊 REPRODUCIR AUDIO", use_container_width=True, type="primary"):
                st.audio(audio_bytes, format='audio/mp3')
                st.caption("💡 Nota: Si no escuchas, desactiva el modo silencio físico del iPhone.")
                
        except Exception as e:
            st.error(f"❌ Error generando audio: {str(e)}")
            st.info("💡 Recarga la página o usa Safari en iPhone")
        
        # INSTRUCCIONES SIMPLES PARA IPHONE
        st.markdown("### 📱 Instrucciones para iPhone:")
        st.markdown("""
        - 🔊 **Usa Safari** (no Chrome/Firefox)
        - 📱 **Activa el sonido** y quita silencio físico
        - 🎧 **Usa auriculares** para mejor experiencia
        - 📶 **WiFi estable** para audio sin interrupciones
        - 🔄 **Recarga página** si no hay sonido
        """)
        
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
        
        # SECCIÓN DE REVELACIÓN SIMPLE
        if st.button("💡 REVELAR SIGNIFICADO"):
            st.session_state.revelado = True
            
        if st.session_state.revelado:
            st.success(f"**Traducción:** {palabra['esp']}")
            st.info(f"**Mnemotecnia:** {palabra['mne']}")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ LO MEMORICÉ"):
                    db.execute("UPDATE palacio SET estado = 'memorizado' WHERE id = ?", (int(palabra['id']),))
                    db.commit()
                    st.session_state.revelado = False
                    st.rerun()
            with col_b:
                if st.button("❌ NO LO SÉ AÚN"):
                    st.session_state.revelado = False
                    st.rerun()

# --- VISTA: REPASO (MODO TEST) ---
elif st.session_state.vista == 'Repaso':
    st.subheader("🔄 Test de Validación")
    df_mem = pd.read_sql_query("SELECT * FROM palacio WHERE estado = 'memorizado'", db)
    
    if len(df_mem) < 4:
        st.warning("Necesitas memorizar al menos 4 palabras en el entrenamiento antes de repasar.")
    else:
        # Generar pregunta aleatoria de las memorizadas
        if 'test_item' not in st.session_state:
            target = df_mem.sample(1).iloc[0]
            distractores = df_mem[df_mem['id'] != target['id']].sample(3)['esp'].tolist()
            opciones = [target['esp']] + distractores
            random.shuffle(opciones)
            st.session_state.test_item = {'target': target, 'opciones': opciones}

        t = st.session_state.test_item
        st.markdown(f'<div class="card"><h1>{t["target"]["ruso"]}</h1></div>', unsafe_allow_html=True)
        
        seleccion = st.radio("¿Cuál es el significado correcto?", t['opciones'])
        
        if st.button("Comprobar Respuesta"):
            if seleccion == t['target']['esp']:
                st.balloons()
                st.success("¡Excelente! Memoria confirmada.")
                if st.button("Siguiente Test"):
                    del st.session_state.test_item
                    st.rerun()
            else:
                st.error(f"¡Cuidado! El significado era: {t['target']['esp']}")
                if st.button("Devolver a entrenamiento"):
                    db.execute("UPDATE palacio SET estado = 'nuevo' WHERE id = ?", (int(t['target']['id']),))
                    db.commit()
                    del st.session_state.test_item
                    st.rerun()

# --- VISTA: PALACIO (CORREGIDA LA VISIBILIDAD DE ESTADO) ---
elif st.session_state.vista == 'Palacio':
    st.subheader("🏰 Tu Palacio de la Memoria")
    df_total = pd.read_sql_query("SELECT ruso, esp, mne, ubicacion, estado FROM palacio", db)
    
    if df_total.empty:
        st.info("Tu palacio está vacío.")
    else:
        # Mostrar contadores
        m = len(df_total[df_total['estado'] == 'memorizado'])
        n = len(df_total[df_total['estado'] != 'memorizado'])
        c1, c2 = st.columns(2)
        c1.metric("Memorizadas", m)
        c2.metric("Pendientes", n)

        # Buscador sencillo
        search = st.text_input("Buscar palabra en el palacio...")
        if search:
            df_total = df_total[df_total['ruso'].str.contains(search) | df_total['esp'].str.contains(search)]

        # Lista visual del palacio
        for _, fila in df_total.iterrows():
            color = "#D1FAE5" if fila['estado'] == 'memorizado' else "#FEE2E2"
            texto_estado = "✅ MEMORIZADA" if fila['estado'] == 'memorizado' else "⏳ PENDIENTE"
            
            st.markdown(f"""
                <div style="background-color: {color}; padding: 15px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #ccc;">
                    <span style="float: right;" class="status-tag">{texto_estado}</span>
                    <b style="font-size: 18px;">{fila['ruso']}</b> — {fila['esp']}<br>
                    <small>📍 {fila['ubicacion']} | 💭 {fila['mne']}</small>
                </div>
                """, unsafe_allow_html=True)

# --- VISTA: CARGAR ---
elif st.session_state.vista == 'Cargar':
    st.subheader("📥 Cargar Nuevas Palabras")
    archivo = st.file_uploader("Sube tu CSV (columnas: ruso, trans, esp, mne, ubicacion)", type=['csv'])
    
    if archivo:
        try:
            nuevo_df = pd.read_csv(archivo)
            # Limpieza de nombres de columnas
            nuevo_df.columns = [c.lower().strip() for c in nuevo_df.columns]
            cols_necesarias = ['ruso', 'trans', 'esp', 'mne', 'ubicacion']
            
            if all(c in nuevo_df.columns for c in cols_necesarias):
                df_to_save = nuevo_df[cols_necesarias].copy()
                df_to_save['estado'] = 'nuevo'
                df_to_save.to_sql('palacio', db, if_exists='append', index=False)
                st.success(f"¡{len(df_to_save)} palabras añadidas al palacio!")
            else:
                st.error("El CSV no tiene las columnas correctas.")
        except Exception as e:
            st.error(f"Error al procesar: {e}")

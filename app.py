import os
import subprocess
import shlex
import logging
import threading
import telebot
import shutil
import tempfile
import time
from telebot.types import InputFile
from werkzeug.utils import secure_filename
from flask import Flask, request
import traceback

# Configuración
UPLOAD_FOLDER = os.path.abspath("uploads")
YOUTUBE_FOLDER = os.path.abspath("youtube_downloads")
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU')
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Asegurar directorios
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

# Inicializar bot y sesiones de usuario
bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}
app = Flask(__name__)

# --- Funciones auxiliares mejoradas ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

def validate_path(base_dir, target_path):
    """Valida que la ruta esté dentro del directorio base permitido"""
    try:
        base_dir = os.path.abspath(base_dir)
        target_path = os.path.abspath(target_path)
        return os.path.commonpath([base_dir, target_path]) == base_dir
    except Exception:
        return False

def execute_command(session_id, command):
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            "history": [],
            "cwd": os.getcwd(),
            "base_dir": os.getcwd()
        }
    
    session_info = user_sessions[session_id]
    output = ""
    
    try:
        if command.startswith("cd "):
            parts = shlex.split(command, posix=True)
            if len(parts) < 2:
                raise ValueError("Directorio no especificado")
            
            new_dir = ' '.join(parts[1:])
            target = os.path.normpath(os.path.join(session_info["cwd"], new_dir))
            
            if not validate_path(session_info["base_dir"], target):
                raise ValueError("Acceso a directorio no permitido")
            
            if not os.path.isdir(target):
                raise FileNotFoundError(f"Directorio no encontrado: {target}")
            
            session_info["cwd"] = target
            output = f"Directorio actual: {session_info['cwd']}"
        else:
            args = shlex.split(command, posix=True)
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=session_info["cwd"],
                env={'PATH': os.getenv('PATH', '')}
            )
            stdout, stderr = proc.communicate(timeout=30)
            output = stdout + stderr
            if proc.returncode != 0:
                output += f"\n[Código salida: {proc.returncode}]"
                
    except Exception as e:
        output = f"Error: {str(e)}"
        logging.error(f"Error ejecutando comando: {traceback.format_exc()}")
    
    session_info["history"].append(f"$ {command}\n{output}")
    session_info["history"] = clean_history(session_info["history"])
    return output

# --- Handlers mejorados ---
@bot.message_handler(commands=['start', 'help', 'ayuda'])
def send_help(message):
    help_text = """
<b>Consola Web Bot</b>

<b>Comandos disponibles:</b>
/start, /ayuda - Mostrar ayuda
/ejecutar &lt;comando&gt; - Ejecutar comando en la terminal
/cd &lt;directorio&gt; - Cambiar directorio
/historial - Mostrar últimos comandos
/archivos - Listar archivos subidos
/subir - Subir archivo .py (envía el archivo)
/eliminar &lt;nombre&gt; - Eliminar archivo subido
/descargar &lt;URL&gt; - Descargar video de YouTube en partes ZIP
"""
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

@bot.message_handler(commands=['ejecutar'])
def handle_execute(message):
    try:
        cmd = message.text.split(maxsplit=1)[1]
        out = execute_command(str(message.chat.id), cmd)
        bot.send_message(message.chat.id, f"<pre>{out}</pre>", parse_mode='HTML')
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /ejecutar &lt;comando&gt;", parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f"<b>Error crítico:</b>\n<pre>{str(e)}</pre>", parse_mode='HTML')

@bot.message_handler(commands=['descargar'])
def handle_download(message):
    try:
        url = message.text.split(maxsplit=1)[1]
        bot.reply_to(message, "⏳ Iniciando descarga...")
        
        # Limpiar descargas previas
        shutil.rmtree(YOUTUBE_FOLDER, ignore_errors=True)
        os.makedirs(YOUTUBE_FOLDER, exist_ok=True)
        
        # Configurar entorno para ffmpeg
        env = os.environ.copy()
        env['PATH'] = f"/opt/render/project/src/bin:{env.get('PATH', '')}"
        
        # Ejecutar downloader.py en segundo plano
        def download_task():
            try:
                cmd = ['python3', 'downloader.py', url]
                result = subprocess.run(
                    cmd,
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=600  # 10 minutos máximo
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or "Error desconocido"
                    bot.send_message(message.chat.id, f"❌ Error en descarga:\n<pre>{error_msg}</pre>", parse_mode='HTML')
                    return
                
                # Enviar archivos ZIP
                zips = sorted(f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip'))
                if not zips:
                    bot.send_message(message.chat.id, "⚠️ No se encontraron archivos descargados")
                    return
                
                for i, zip_file in enumerate(zips, 1):
                    with open(os.path.join(YOUTUBE_FOLDER, zip_file), 'rb') as f:
                        bot.send_document(
                            message.chat.id,
                            InputFile(f),
                            caption=f"Parte {i}/{len(zips)}",
                            timeout=60
                        )
                
                bot.send_message(message.chat.id, "✅ Descarga completada!")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error interno:\n<pre>{str(e)}</pre>", parse_mode='HTML')
                logging.error(f"Error en descarga: {traceback.format_exc()}")
        
        threading.Thread(target=download_task, daemon=True).start()
        
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /descargar &lt;URL&gt;", parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error:\n<pre>{str(e)}</pre>", parse_mode='HTML')

# ... (otros handlers se mantienen similares pero con mejor manejo de errores) ...

# --- Flask App ---
@app.route('/')
def index():
    return "Telegram Bot en ejecución"

@app.route('/health')
def health_check():
    return "OK", 200

def start_bot():
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as e:
            logging.error(f"Error en polling: {str(e)}\n{traceback.format_exc()}")
            time.sleep(10)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=start_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

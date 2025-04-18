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
from flask import Flask

# Configuración
UPLOAD_FOLDER = os.path.abspath("uploads")
YOUTUBE_FOLDER = os.path.abspath("youtube_downloads")
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100
TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'
FFMPEG_PATH = "/opt/render/project/src/bin/ffmpeg"
FFPROBE_PATH = "/opt/render/project/src/bin/ffprobe"

# Asegurar directorios
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

# Inicializar bot y sesiones de usuario
bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}
app = Flask(__name__)

# --- Funciones mejoradas ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

def validate_path(base_dir, target_path):
    """Valida que la ruta esté dentro del directorio base permitido"""
    return os.path.commonpath([base_dir, os.path.abspath(target_path)]) == base_dir

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
        # Manejo especial para ffmpeg
        if command.startswith("ffmpeg "):
            command = command.replace("--version", "-version", 1)
            
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
            env = os.environ.copy()
            env["PATH"] = f"/opt/render/project/src/bin:{env.get('PATH', '')}"
            
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=session_info["cwd"],
                env=env
            )
            stdout, stderr = proc.communicate(timeout=30)
            output = stdout + stderr
            if proc.returncode != 0:
                output += f"\n[Código salida: {proc.returncode}]"
                
    except Exception as e:
        output = f"Error: {str(e)}"
        logging.error(f"Error ejecutando comando: {command}\n{str(e)}")
    
    session_info["history"].append(f"$ {command}\n{output}")
    session_info["history"] = clean_history(session_info["history"])
    return output

# --- Handlers actualizados ---
@bot.message_handler(commands=['descargar'])
def handle_download(message):
    try:
        url = message.text.split(maxsplit=1)[1].split('?')[0]  # Limpiar parámetros de URL
        
        # Verificación previa de URL
        if not any(domain in url for domain in ['youtube.com', 'youtu.be']):
            bot.reply_to(message, "❌ URL de YouTube no válida")
            return
            
        bot.reply_to(message, "⏳ Iniciando descarga...")
        
        # Configurar entorno para ffmpeg
        env = os.environ.copy()
        env.update({
            "PATH": f"/opt/render/project/src/bin:{env.get('PATH', '')}",
            "FFMPEG_PATH": FFMPEG_PATH,
            "FFPROBE_PATH": FFPROBE_PATH
        })
        
        # Ejecutar en segundo plano
        def download_task():
            try:
                cmd = ['python3', 'downloader.py', url]
                result = subprocess.run(
                    cmd,
                    cwd=os.getcwd(),
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=600
                )
                
                if result.returncode != 0:
                    error_msg = result.stderr or "Error desconocido"
                    bot.send_message(message.chat.id, f"❌ Error en descarga:\n<pre>{error_msg}</pre>", parse_mode='HTML')
                    return
                
                # Enviar archivos ZIP
                zips = sorted(f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip'))
                for i, fname in enumerate(zips, 1):
                    with open(os.path.join(YOUTUBE_FOLDER, fname), 'rb') as f:
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
        bot.send_message(message.chat.id, "Uso: /descargar <URL>")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error:\n<pre>{str(e)}</pre>", parse_mode='HTML')

# ... (resto de handlers se mantienen igual) ...

# --- Verificación de entorno ---
@bot.message_handler(commands=['verificar'])
def check_environment(message):
    """Verificar dependencias críticas"""
    checks = [
        ("FFmpeg", [FFMPEG_PATH, "-version"]),
        ("FFprobe", [FFPROBE_PATH, "-version"]),
        ("yt-dlp", ["yt-dlp", "--version"])
    ]
    
    report = []
    for name, cmd in checks:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10
            )
            version = result.stdout.split('\n')[0] if result.stdout else "?"
            report.append(f"✅ {name}: {version.split(' ')[0]}")
        except Exception as e:
            report.append(f"❌ {name}: Error ({str(e)})")
    
    bot.send_message(message.chat.id, "\n".join(report))

# --- Inicio de Flask ---
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

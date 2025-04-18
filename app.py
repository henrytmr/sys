import os
import subprocess
import shlex
import logging
import threading
import telebot
import shutil
import tempfile
import time
import traceback
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

# --- Funciones principales mejoradas ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

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
        # Corrección automática para comandos ffmpeg
        corrected_command = command.replace("--version", "-version") if "ffmpeg" in command else command
        
        if corrected_command.startswith("cd "):
            parts = shlex.split(corrected_command, posix=True)
            if len(parts) < 2:
                raise ValueError("Directorio no especificado")
            
            new_dir = ' '.join(parts[1:])
            target = os.path.normpath(os.path.join(session_info["cwd"], new_dir))
            
            if not os.path.commonpath([session_info["base_dir"], target]) == session_info["base_dir"]:
                raise ValueError("Acceso a directorio no permitido")
            
            if not os.path.isdir(target):
                raise FileNotFoundError(f"Directorio no encontrado: {target}")
            
            session_info["cwd"] = target
            output = f"Directorio actual: {session_info['cwd']}"
        else:
            env = os.environ.copy()
            env["PATH"] = f"/opt/render/project/src/bin:{env.get('PATH', '')}"
            
            proc = subprocess.Popen(
                shlex.split(corrected_command, posix=True),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=session_info["cwd"],
                env=env
            )
            stdout, stderr = proc.communicate(timeout=20)
            output = stdout + stderr
            if proc.returncode != 0:
                output += f"\n[Código salida: {proc.returncode}]"
                
    except Exception as e:
        output = f"Error: {str(e)}"
        logging.error(f"Error en comando '{command}': {traceback.format_exc()}")
    
    session_info["history"].append(f"$ {command}\n{output}")
    session_info["history"] = clean_history(session_info["history"])
    return output

# --- Handler de descarga mejorado ---
@bot.message_handler(commands=['descargar'])
def download_youtube(message):
    try:
        url = message.text.split(maxsplit=1)[1].split('?')[0]  # Limpiar parámetros URL
        
        if not any(dominio in url for dominio in ['youtube.com', 'youtu.be']):
            bot.reply_to(message, "❌ URL de YouTube no válida")
            return
            
        bot.reply_to(message, "⏳ Procesando solicitud...")
        
        # Configurar entorno para ffmpeg
        env = os.environ.copy()
        env.update({
            "PATH": f"/opt/render/project/src/bin:{env['PATH']}",
            "FFMPEG_PATH": FFMPEG_PATH,
            "FFPROBE_PATH": FFPROBE_PATH
        })
        
        def tarea_descarga():
            try:
                # Ejecutar downloader.py con entorno modificado
                resultado = subprocess.run(
                    ['python3', 'downloader.py', url],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=600  # 10 minutos máximo
                )
                
                if resultado.returncode != 0:
                    error = resultado.stderr or "Error desconocido"
                    bot.send_message(message.chat.id, f"❌ Fallo en descarga:\n```\n{error}\n```", parse_mode='Markdown')
                    return
                
                # Enviar archivos resultantes
                zips = sorted([f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip')], key=lambda x: int(x.split('.')[0]))
                for i, archivo in enumerate(zips, 1):
                    with open(os.path.join(YOUTUBE_FOLDER, archivo), 'rb') as f:
                        bot.send_document(
                            message.chat.id,
                            InputFile(f),
                            caption=f"Parte {i}/{len(zips)}",
                            timeout=60
                        )
                bot.send_message(message.chat.id, "✅ Descarga completada!")
            except Exception as e:
                bot.send_message(message.chat.id, f"🔥 Error crítico:\n```\n{str(e)}\n```", parse_mode='Markdown')
                logging.error(f"Error en descarga: {traceback.format_exc()}")
        
        threading.Thread(target=tarea_descarga, daemon=True).start()
        
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /descargar <URL>")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Error inicial: {str(e)}")

# ... (resto de handlers se mantienen igual) ...

# --- Configuración Flask ---
def start_bot():
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=25)
        except Exception as e:
            logging.error(f"Error en polling: {str(e)}\n{traceback.format_exc()}")
            time.sleep(10)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=start_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

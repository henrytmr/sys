import os
import subprocess
import shlex
import logging
import threading
import telebot
import shutil
import tempfile
from telebot.types import InputFile
from werkzeug.utils import secure_filename
from flask import Flask

# Configuración
UPLOAD_FOLDER = os.path.abspath("uploads")
YOUTUBE_FOLDER = os.path.abspath("youtube_downloads")
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100
TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'

# Asegurar directorios
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

# Inicializar bot y usuario sesiones
bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

def execute_command(session_id, command):
    if session_id not in user_sessions:
        user_sessions[session_id] = {"history": [], "cwd": os.getcwd()}
    session_info = user_sessions[session_id]
    output = ""
    try:
        if command.startswith("cd "):
            # Manejo seguro de rutas con espacios
            parts = shlex.split(command, posix=True)
            if len(parts) < 2:
                raise ValueError("Directorio no especificado")
            
            new_dir = ' '.join(parts[1:])
            # Sanitización de ruta
            new_dir = os.path.normpath(new_dir).replace("\\", "/").lstrip('/')
            new_dir = new_dir.replace("../", "").replace("..", "")  # Prevenir path traversal
            
            target = os.path.join(session_info["cwd"], new_dir)
            if not os.path.isdir(target):
                raise FileNotFoundError(f"Directorio no encontrado: {target}")
            
            os.chdir(target)
            session_info["cwd"] = os.getcwd()
            output = f"Directorio actual: {session_info['cwd']}"
        else:
            # Parseo robusto de comandos
            args = shlex.split(command, posix=True)
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=session_info["cwd"]
            )
            stdout, stderr = proc.communicate(timeout=15)
            output = stdout + stderr
            if proc.returncode != 0:
                output += f"\n[Código salida: {proc.returncode}]"
    except Exception as e:
        output = f"Error: {str(e)}"
    
    session_info["history"].append(f"$ {command}\n{output}")
    session_info["history"] = clean_history(session_info["history"])
    return output

# ----- Handlers Consola y Archivos -----

@bot.message_handler(commands=['start', 'ayuda'])
def send_help(message):
    help_text = (
        "Consola Web Bot\n\n"
        "Comandos disponibles:\n"
        "/start, /ayuda         - Mostrar ayuda\n"
        "/ejecutar <comando>    - Ejecutar comando en la terminal\n"
        "/cd <directorio>       - Cambiar directorio\n"
        "/historial             - Mostrar últimos comandos\n"
        "/archivos              - Listar archivos subidos\n"
        "/subir                 - Subir archivo .py (envía el archivo)\n"
        "/eliminar <nombre>     - Eliminar archivo subido\n"
        "/descargar <URL>       - Descargar video de YouTube en partes ZIP\n"
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['ejecutar'])
def handle_execute(message):
    try:
        cmd = message.text.split(maxsplit=1)[1]  # Captura todo después de /ejecutar
        out = execute_command(str(message.chat.id), cmd)
        bot.send_message(message.chat.id, f"```\n{out}\n```", parse_mode='Markdown')
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /ejecutar <comando>")
    except Exception as e:
        bot.send_message(message.chat.id, f"Error crítico: {str(e)}")

@bot.message_handler(commands=['cd'])
def change_dir(message):
    try:
        path = message.text.split(maxsplit=1)[1]
        out = execute_command(str(message.chat.id), f"cd {path}")
        bot.send_message(message.chat.id, out)
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /cd <directorio>")

# ... (Los demás handlers permanecen igual, desde @bot.message_handler(commands=['historial']) hasta el final)

# ----- Flask + Bot polling -----

app = Flask(__name__)

@app.route('/')
def index():
    return "Telegram Bot en ejecución"

def start_bot():
    while True:
        try:
            bot.infinity_polling()
        except Exception:
            logging.exception("Fallo polling, reiniciando en 5s…")
            time.sleep(5)

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
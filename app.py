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

# Configuracion
UPLOAD_FOLDER = os.path.abspath("uploads")
YOUTUBE_FOLDER = os.path.abspath("youtube_downloads")
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100
TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'

# Asegurar directorios
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

# Inicializar bot
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
            new_dir = command[3:].strip()
            target = os.path.join(session_info["cwd"], new_dir)
            os.chdir(target)
            session_info["cwd"] = os.getcwd()
            output = "Directorio actual: " + session_info["cwd"]
        else:
            process = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=session_info["cwd"]
            )
            stdout, stderr = process.communicate(timeout=15)
            output = stdout + stderr
            if process.returncode != 0:
                output += f"\n[Codigo salida: {process.returncode}]"
    except Exception as e:
        output = f"Error: {str(e)}"
    session_info["history"].append(f"$ {command}\n{output}")
    session_info["history"] = clean_history(session_info["history"])
    return output

@bot.message_handler(commands=['start', 'ayuda'])
def send_help(message):
    help_text = (
        "Consola Web Bot\n\n"
        "Comandos disponibles:\n"
        "/start - Iniciar el bot\n"
        "/ayuda - Mostrar esta ayuda\n"
        "/ejecutar <comando> - Ejecutar comando en la terminal\n"
        "/archivos - Listar archivos subidos\n"
        "/subir - Subir archivo .py (envia el archivo como documento)\n"
        "/eliminar <nombre> - Eliminar archivo\n"
        "/cd <directorio> - Cambiar directorio\n"
        "/historial - Mostrar ultimos comandos\n"
        "/descarga <URL> - Descargar video de YouTube y enviarlo en partes"
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['ejecutar'])
def handle_execute(message):
    try:
        command = message.text.split(' ', 1)[1]
        session_id = str(message.chat.id)
        output = execute_command(session_id, command)
        bot.send_message(message.chat.id, "```\n" + output + "\n```", parse_mode='Markdown')
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /ejecutar <comando>")

@bot.message_handler(commands=['archivos'])
def list_files(message):
    files = os.listdir(UPLOAD_FOLDER)
    response = "Archivos subidos:\n" + "\n".join(files) if files else "No hay archivos subidos"
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['historial'])
def show_history(message):
    session_id = str(message.chat.id)
    if session_id in user_sessions:
        history = "\n".join(user_sessions[session_id]["history"])
        bot.send_message(message.chat.id, "Historial:\n" + history)
    else:
        bot.send_message(message.chat.id, "No hay historial aun.")

@bot.message_handler(commands=['eliminar'])
def delete_file(message):
    try:
        filename = message.text.split(' ', 1)[1]
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            bot.send_message(message.chat.id, f"Archivo {filename} eliminado.")
        else:
            bot.send_message(message.chat.id, "Archivo no encontrado.")
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /eliminar <nombre>")

@bot.message_handler(commands=['descarga'])
def handle_descarga(message):
    try:
        url = message.text.split(' ', 1)[1]
        threading.Thread(target=process_youtube_download, args=(message, url)).start()
    except IndexError:
        bot.reply_to(message, "Uso: /descarga <URL de YouTube>")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

def process_youtube_download(message, url):
    chat_id = message.chat.id
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(dir=YOUTUBE_FOLDER)
        video_path = os.path.join(temp_dir, "video.mp4")
        yt_dlp_cmd = [
            'yt-dlp',
            '-f', 'best',
            '-o', video_path,
            url
        ]
        result = subprocess.run(yt_dlp_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Error descargando video: {result.stderr}")

        zip_base = os.path.join(temp_dir, "output.zip")
        zip_cmd = [
            'zip',
            '-r',
            '-s', '60m',
            zip_base,
            video_path
        ]
        result = subprocess.run(zip_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Error creando ZIP: {result.stderr}")

        split_files = [f for f in os.listdir(temp_dir) if f.startswith("output.z") or f == "output.zip"]

        def sort_key(f):
            if f == "output.zip":
                return (1, 0)
            parts = f.split(".z")
            return (0, int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0)

        split_files.sort(key=sort_key)

        for i, filename in enumerate(split_files, 1):
            src = os.path.join(temp_dir, filename)
            dest = os.path.join(temp_dir, f"{i}.zip")
            os.rename(src, dest)
            with open(dest, 'rb') as f:
                bot.send_document(chat_id, InputFile(f))

    except Exception as e:
        bot.send_message(chat_id, f"Error: {str(e)}")
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

@bot.message_handler(content_types=['document'])
def handle_file(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        filename = secure_filename(message.document.file_name)
        if not allowed_file(filename):
            raise ValueError("Solo se permiten archivos .py")
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        with open(filepath, 'wb') as new_file:
            new_file.write(downloaded_file)
        bot.reply_to(message, f"Archivo {filename} subido correctamente.")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

# Flask app
app = Flask(__name__)

@app.route('/')
def index():
    return "Telegram Bot en ejecución"

def start_bot():
    bot.infinity_polling()

threading.Thread(target=start_bot, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
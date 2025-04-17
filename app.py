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
# o usa os.getenv("TELEGRAM_TOKEN")

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
            new_dir = command[3:].strip()
            target = os.path.join(session_info["cwd"], new_dir)
            os.chdir(target)
            session_info["cwd"] = os.getcwd()
            output = "Directorio actual: " + session_info["cwd"]
        else:
            proc = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=session_info["cwd"]
            )
            stdout, stderr = proc.communicate(timeout=15)
            output = stdout + stderr
            if proc.returncode != 0:
                output += f"\n[Codigo salida: {proc.returncode}]"
    except Exception as e:
        output = f"Error: {e}"
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
        cmd = message.text.split(' ', 1)[1]
        out = execute_command(str(message.chat.id), cmd)
        bot.send_message(message.chat.id, f"```\n{out}\n```", parse_mode='Markdown')
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /ejecutar <comando>")

@bot.message_handler(commands=['cd'])
def change_dir(message):
    try:
        path = message.text.split(' ', 1)[1]
        out = execute_command(str(message.chat.id), f"cd {path}")
        bot.send_message(message.chat.id, out)
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /cd <directorio>")

@bot.message_handler(commands=['historial'])
def show_history(message):
    sid = str(message.chat.id)
    if sid in user_sessions:
        history = "\n".join(user_sessions[sid]["history"])
        bot.send_message(message.chat.id, f"Historial:\n{history}")
    else:
        bot.send_message(message.chat.id, "No hay historial aún.")

@bot.message_handler(commands=['archivos'])
def list_files(message):
    files = os.listdir(UPLOAD_FOLDER)
    resp = "Archivos subidos:\n" + "\n".join(files) if files else "No hay archivos subidos"
    bot.send_message(message.chat.id, resp)

@bot.message_handler(commands=['eliminar'])
def delete_file(message):
    try:
        fname = message.text.split(' ', 1)[1]
        fp = os.path.join(UPLOAD_FOLDER, secure_filename(fname))
        if os.path.exists(fp):
            os.remove(fp)
            bot.send_message(message.chat.id, f"Archivo {fname} eliminado.")
        else:
            bot.send_message(message.chat.id, "Archivo no encontrado.")
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /eliminar <nombre>")

@bot.message_handler(content_types=['document'])
def handle_upload(message):
    try:
        finfo = bot.get_file(message.document.file_id)
        data = bot.download_file(finfo.file_path)
        name = secure_filename(message.document.file_name)
        if not allowed_file(name):
            raise ValueError("Solo archivos .py permitidos")
        with open(os.path.join(UPLOAD_FOLDER, name), 'wb') as f:
            f.write(data)
        bot.reply_to(message, f"Archivo {name} subido correctamente.")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# ----- /descargar -> invocar downloader.py -----

@bot.message_handler(commands=['descargar'])
def handle_descarga(message):
    try:
        url = message.text.split(' ', 1)[1]
        bot.reply_to(message, f"Iniciando descarga: {url}")
        threading.Thread(target=run_download, args=(message.chat.id, url), daemon=True).start()
    except IndexError:
        bot.reply_to(message, "Uso: /descargar <URL>")

def run_download(chat_id, url):
    try:
        # limpia descargas previas
        shutil.rmtree(YOUTUBE_FOLDER, ignore_errors=True)
        os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

        # llama al script downloader.py
        cmd = ['python3', 'downloader.py', url]
        res = subprocess.run(cmd, cwd=os.getcwd(), capture_output=True, text=True)
        if res.returncode != 0:
            bot.send_message(chat_id, f"Error descarga:\n{res.stderr}")
            return

        # envía cada ZIP
        zips = sorted(f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip'))
        for i, fname in enumerate(zips, 1):
            path = os.path.join(YOUTUBE_FOLDER, fname)
            with open(path, 'rb') as f:
                bot.send_document(chat_id, InputFile(f), caption=f"{i}/{len(zips)}")
        bot.send_message(chat_id, "✅ Descarga completa.")
    except Exception as e:
        bot.send_message(chat_id, f"Error interno: {e}")

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
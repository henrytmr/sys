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

# ... (funciones allowed_file, clean_history, execute_command y handlers anteriores) ...

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
        # Limpia descargas previas
        shutil.rmtree(YOUTUBE_FOLDER, ignore_errors=True)
        os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

        # Configurar entorno para incluir ffmpeg
        env = os.environ.copy()
        env["PATH"] = f"/opt/render/project/src/bin:{env['PATH']}"

        # Ejecutar downloader.py con el entorno modificado
        cmd = ['python3', 'downloader.py', url]
        res = subprocess.run(
            cmd, 
            cwd=os.getcwd(), 
            capture_output=True, 
            text=True, 
            env=env  # Pasar el entorno personalizado
        )

        if res.returncode != 0:
            error_msg = f"Error descarga:\n{res.stderr}" if res.stderr else "Error desconocido"
            bot.send_message(chat_id, error_msg)
            return

        # Enviar archivos ZIP
        zips = sorted(f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip'))
        for i, fname in enumerate(zips, 1):
            path = os.path.join(YOUTUBE_FOLDER, fname)
            with open(path, 'rb') as f:
                bot.send_document(chat_id, InputFile(f), caption=f"{i}/{len(zips)}")
        bot.send_message(chat_id, "✅ Descarga completa.")
    except Exception as e:
        bot.send_message(chat_id, f"Error interno: {e}")

# ... (código de Flask y polling al final del archivo) ...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

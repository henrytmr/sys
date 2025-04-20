#!/data/data/com.termux/files/usr/bin/env python3
import os
import sys
import subprocess
import logging
import threading
import time
import re
from telebot.types import InputFile
import telebot
from flask import Flask
from pyrogram import Client
from pyrogram.errors import FloodWait
import asyncio

# Configuración
API_ID = 12345678         # Reemplaza con tu API_ID
API_HASH = 'your_api_hash'  # Reemplaza con tu API_HASH
SESSION_NAME = 'mi_sesion_telegram'
TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
DOWNLOAD_FOLDER = os.path.join(SCRIPT_DIR, "Telegram_Downloads")
UPLOAD_FOLDER = os.path.join(SCRIPT_DIR, "uploads")
YOUTUBE_FOLDER = os.path.join(SCRIPT_DIR, "youtube_downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
session_states = {}
user_sessions = {}

# Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Descargar medios desde enlaces t.me
async def descargar_telegram_media(url):
    if not re.match(r'https://t.me/\S+/\d+', url):
        return "URL inválida"

    match = re.findall(r'https://t.me/([\w_]+)/(\d+)', url)
    if not match:
        return "No se pudo extraer canal y mensaje"

    canal, msg_id = match[0]
    async with Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH) as app:
        try:
            mensaje = await app.get_messages(canal, int(msg_id))
            media = mensaje.document or mensaje.video or mensaje.audio or mensaje.photo
            if not media:
                return f"No hay media en el mensaje {url}"

            file_path = await mensaje.download(file_name=DOWNLOAD_FOLDER)
            return f"Descargado: {file_path}"
        except Exception as e:
            return f"Error al descargar {url}:\n{str(e)}"

def run_async_download(urls):
    return asyncio.run(_download_batch(urls))

async def _download_batch(urls):
    resultados = []
    for url in urls:
        resultado = await descargar_telegram_media(url)
        resultados.append(resultado)
    return resultados

# — Comandos básicos —
@bot.message_handler(commands=["start", "ayuda"])
def help_handler(m):
    bot.send_message(m.chat.id, (
        "Bot Termux — Descargas Telegram\n\n"
        "/start, /ayuda        - Ayuda\n"
        "/ejecutar <cmd>       - Ejecutar shell\n"
        "/cd <dir>             - Cambiar directorio\n"
        "/historial            - Historial\n"
        "/archivos             - Listar subidos\n"
        "/subir                - Subir .py/.txt/.zip\n"
        "/eliminar <archivo>   - Borrar upload\n"
        "/descargar <URL>      - YouTube\n"
        "/downloader <URLs>    - Media t.me\n\n"
        "Ejemplo:\n"
        "`/downloader https://t.me/canal/123 https://t.me/otro/456`"
    ), parse_mode="Markdown")

@bot.message_handler(commands=["ejecutar"])
def shell_exec(m):
    try:
        cmd = m.text.split(" ",1)[1]
        uid = str(m.chat.id)
        sess = user_sessions.setdefault(uid, {"cwd": SCRIPT_DIR, "hist": []})
        res = subprocess.run(cmd, shell=True, cwd=sess["cwd"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, timeout=15)
        out = res.stdout + res.stderr
        sess["hist"].append(f"$ {cmd}\n{out}")
        sess["hist"] = sess["hist"][-50:]
        bot.send_message(m.chat.id, f"```\n{out}\n```", parse_mode="Markdown")
    except:
        bot.send_message(m.chat.id, "Uso: /ejecutar <cmd>")

@bot.message_handler(commands=["cd"])
def change_dir(m):
    try:
        path = m.text.split(" ",1)[1]
        uid = str(m.chat.id)
        sess = user_sessions.setdefault(uid, {"cwd": SCRIPT_DIR, "hist": []})
        new = os.path.abspath(os.path.join(sess["cwd"], path))
        if os.path.isdir(new):
            sess["cwd"] = new
            bot.send_message(m.chat.id, f"Directorio: {new}")
        else:
            bot.send_message(m.chat.id, f"No existe: {new}")
    except:
        bot.send_message(m.chat.id, "Uso: /cd <dir>")

@bot.message_handler(commands=["historial"])
def show_history(m):
    hist = user_sessions.get(str(m.chat.id), {}).get("hist", [])
    if hist:
        bot.send_message(m.chat.id, "```\n"+ "\n".join(hist)+"\n```", parse_mode="Markdown")
    else:
        bot.send_message(m.chat.id, "Historial vacío")

@bot.message_handler(commands=["archivos"])
def list_uploads(m):
    lst = os.listdir(UPLOAD_FOLDER)
    txt = "\n".join(lst) if lst else "No hay archivos"
    bot.send_message(m.chat.id, f"```\n{txt}\n```", parse_mode="Markdown")

@bot.message_handler(commands=["subir"])
def prompt_upload(m):
    bot.send_message(m.chat.id, "Envía tu `.py`, `.txt` o `.zip` como documento")

@bot.message_handler(content_types=["document"])
def receive_upload(m):
    fn = m.document.file_name
    if not fn.lower().endswith(('.py','.txt','.zip')):
        return bot.send_message(m.chat.id, "Solo .py / .txt / .zip")
    info = bot.get_file(m.document.file_id)
    data = bot.download_file(info.file_path)
    with open(os.path.join(UPLOAD_FOLDER, fn), "wb") as f:
        f.write(data)
    bot.send_message(m.chat.id, f"Archivo subido: {fn}")

@bot.message_handler(commands=["eliminar"])
def delete_upload(m):
    try:
        fn = m.text.split(" ",1)[1]
        p = os.path.join(UPLOAD_FOLDER, fn)
        if os.path.exists(p):
            os.remove(p)
            bot.send_message(m.chat.id, f"Eliminado: {fn}")
        else:
            bot.send_message(m.chat.id, "No existe ese archivo")
    except:
        bot.send_message(m.chat.id, "Uso: /eliminar <archivo>")

@bot.message_handler(commands=["descargar"])
def youtube_dl(m):
    try:
        url = m.text.split(" ",1)[1]
        subprocess.run(f"rm -f {YOUTUBE_FOLDER}/*.zip", shell=True)
        res = subprocess.run([sys.executable, "-m", "yt_dlp", url, "-o", f"{YOUTUBE_FOLDER}/%(title)s.%(ext)s", "-f", "bestvideo+bestaudio"], text=True)
        for f in os.listdir(YOUTUBE_FOLDER):
            if f.endswith(".mp4") or f.endswith(".mkv") or f.endswith(".zip"):
                bot.send_document(m.chat.id, InputFile(os.path.join(YOUTUBE_FOLDER, f)))
    except:
        bot.send_message(m.chat.id, "Uso: /descargar <URL>")

# — /downloader —
@bot.message_handler(commands=["downloader"])
def downloader_start(m):
    urls = m.text.split()[1:]
    if not urls:
        return bot.send_message(m.chat.id, "Uso: /downloader <URL1> [URL2...]")
    bot.send_message(m.chat.id, f"Descargando {len(urls)} archivo(s)...")
    resultados = run_async_download(urls)
    for msg in resultados:
        bot.send_message(m.chat.id, msg)
    for fn in os.listdir(DOWNLOAD_FOLDER):
        full = os.path.join(DOWNLOAD_FOLDER, fn)
        if os.path.isfile(full):
            bot.send_document(m.chat.id, InputFile(full), caption=fn)

# Web server + polling
app = Flask(__name__)
@app.route("/")
def home(): return "Bot activo"

def polling():
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

threading.Thread(target=polling, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

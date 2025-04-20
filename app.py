#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
import threading
import re
from telebot import TeleBot
from telebot.types import InputFile
from flask import Flask
from telethon.sync import TelegramClient
from telethon.errors import ChannelPrivateError

# ——— Configuración ———
SCRIPT_DIR         = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER      = os.path.join(SCRIPT_DIR, "uploads")
YOUTUBE_FOLDER     = os.path.join(SCRIPT_DIR, "youtube_downloads")
TELEGRAM_DL_FOLDER = os.path.join(SCRIPT_DIR, "descargas_publicas")
MAX_HISTORY_LINES  = 100

# ——— Tus credenciales ———
TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'
API_ID         = 29246871
API_HASH       = '637091dfc0eee0e2c551fd832341e18b'

# Crear carpetas
os.makedirs(UPLOAD_FOLDER,      exist_ok=True)
os.makedirs(YOUTUBE_FOLDER,     exist_ok=True)
os.makedirs(TELEGRAM_DL_FOLDER, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Instancias
bot = TeleBot(TELEGRAM_TOKEN)
# Telethon en modo bot para no pedir código
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=TELEGRAM_TOKEN)

# Estado por usuario
user_sessions = {}

def send_help(message):
    txt = (
        "Consola Web Bot\n\n"
        "/start, /ayuda               - Mostrar ayuda\n"
        "/ejecutar <cmd>              - Ejecutar en shell\n"
        "/cd <dir>                    - Cambiar directorio\n"
        "/historial                   - Ver historial de comandos\n"
        "/archivos                    - Listar archivos subidos\n"
        "/subir                       - Subir archivo .py\n"
        "/eliminar <name>             - Borrar archivo subido\n"
        "/downloader <URL1> [URL2...] - Descargar YouTube o Telegram\n"
    )
    bot.send_message(message.chat.id, txt)

def execute_command(uid, cmd):
    sess = user_sessions.setdefault(uid, {"cwd": SCRIPT_DIR, "hist": []})
    out = ""
    try:
        if cmd.startswith("cd "):
            new = os.path.abspath(os.path.join(sess["cwd"], cmd[3:].strip()))
            if os.path.isdir(new):
                sess["cwd"] = new
                out = f"Directorio: {new}"
            else:
                out = f"Error: {new} no existe"
        else:
            r = subprocess.run(cmd, shell=True, cwd=sess["cwd"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, timeout=15)
            out = r.stdout + r.stderr
    except Exception as e:
        out = f"Error: {e}"
    sess["hist"].append(f"$ {cmd}\n{out}")
    sess["hist"] = sess["hist"][-MAX_HISTORY_LINES:]
    return out

@bot.message_handler(commands=['start','ayuda'])
def _start(m):
    send_help(m)

@bot.message_handler(commands=['ejecutar'])
def _run(m):
    try:
        cmd = m.text.split(' ',1)[1]
        out = execute_command(str(m.chat.id), cmd)
        bot.send_message(m.chat.id, f"```\n{out}\n```", parse_mode='Markdown')
    except:
        bot.send_message(m.chat.id, "Uso: /ejecutar <cmd>")

@bot.message_handler(commands=['cd'])
def _cd(m):
    try:
        path = m.text.split(' ',1)[1]
        out = execute_command(str(m.chat.id), f"cd {path}")
        bot.send_message(m.chat.id, out)
    except:
        bot.send_message(m.chat.id, "Uso: /cd <dir>")

@bot.message_handler(commands=['historial'])
def _hist(m):
    h = user_sessions.get(str(m.chat.id), {}).get("hist", [])
    if h:
        bot.send_message(m.chat.id, "```\n" + "\n".join(h) + "\n```", parse_mode='Markdown')
    else:
        bot.send_message(m.chat.id, "No hay historial")

@bot.message_handler(commands=['archivos'])
def _files(m):
    lst = os.listdir(UPLOAD_FOLDER)
    if lst:
        bot.send_message(m.chat.id, "```\n" + "\n".join(lst) + "\n```", parse_mode='Markdown')
    else:
        bot.send_message(m.chat.id, "No hay archivos")

@bot.message_handler(content_types=['document'])
def _upload(m):
    fn = m.document.file_name
    if not fn.lower().endswith('.py'):
        return bot.send_message(m.chat.id, "Solo se permiten .py")
    fp = bot.get_file(m.document.file_id).file_path
    data = bot.download_file(fp)
    dst = os.path.join(UPLOAD_FOLDER, fn)
    with open(dst,'wb') as f: f.write(data)
    bot.send_message(m.chat.id, f"Subido: {fn}")

@bot.message_handler(commands=['eliminar'])
def _del(m):
    try:
        fn = m.text.split(' ',1)[1]
        p = os.path.join(UPLOAD_FOLDER, fn)
        if os.path.exists(p):
            os.remove(p)
            bot.send_message(m.chat.id, f"Eliminado: {fn}")
        else:
            bot.send_message(m.chat.id, "No existe")
    except:
        bot.send_message(m.chat.id, "Uso: /eliminar <name>")

def download_telegram_media(url):
    m = re.match(r'https?://t\\.me/(?:s/)?([A-Za-z0-9_]+)/(\\d+)', url)
    if not m:
        raise ValueError("Enlace Telegram no soportado")
    user, mid = m.groups()
    msg = client.get_messages(user, ids=int(mid))
    if not msg or not msg.media:
        raise ValueError("Ese mensaje no contiene medios")
    ext = msg.file.ext or 'mp4'
    fn  = f"{user}_{mid}.{ext}"
    dst = os.path.join(TELEGRAM_DL_FOLDER, fn)
    client.download_media(msg, file=dst)
    return dst

@bot.message_handler(commands=['downloader'])
def _downloader(m):
    urls = m.text.split()[1:]
    if not urls:
        return bot.send_message(m.chat.id, "Uso: /downloader <URL1> [URL2...]")
    for url in urls:
        if 't.me/' in url:
            bot.send_message(m.chat.id, f"🔍 Descargando de Telegram: {url}")
            try:
                fpath = download_telegram_media(url)
                bot.send_document(m.chat.id, InputFile(fpath), caption=os.path.basename(fpath))
            except Exception as e:
                bot.send_message(m.chat.id, f"Error Telegram: {e}")
        else:
            bot.send_message(m.chat.id, f"🔍 Descargando de YouTube: {url}")
            try:
                # limpiar previos
                for f in os.listdir(YOUTUBE_FOLDER):
                    if f.endswith('.zip'):
                        os.remove(os.path.join(YOUTUBE_FOLDER, f))
                dp = os.path.join(SCRIPT_DIR, 'downloader.py')
                r = subprocess.run([sys.executable, dp, url],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, timeout=600)
                if r.returncode != 0:
                    raise Exception(r.stderr.strip())
                for z in sorted(f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip')):
                    bot.send_document(m.chat.id, InputFile(os.path.join(YOUTUBE_FOLDER, z)), caption=z)
            except Exception as e:
                bot.send_message(m.chat.id, f"Error YouTube: {e}")

# Keep‑alive con Flask
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot activo"

def run_bot():
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            logger.error(e)
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)

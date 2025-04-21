#!/usr/bin/env python3
import os
import sys
import subprocess
import logging
import threading
import re
import time
import asyncio

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
TELEGRAM_TOKEN = '6998654254:AAGSqiXJFEl-TXJhCF5TjJj7QyZrIiVCrvI'
API_ID         = 29246871
API_HASH       = '637091dfc0eee0e2c551fd832341e18b'

# Crear carpetas si no existen
os.makedirs(UPLOAD_FOLDER,      exist_ok=True)
os.makedirs(YOUTUBE_FOLDER,     exist_ok=True)
os.makedirs(TELEGRAM_DL_FOLDER, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Instancia TeleBot
bot = TeleBot(TELEGRAM_TOKEN)

# Estado por usuario para /ejecutar
user_sessions = {}

def send_help(message):
    text = (
        "🤖 *Consola Web Bot*\n\n"
        "/start, /ayuda               - Mostrar ayuda\n"
        "/ejecutar `<cmd>`            - Ejecutar en shell\n"
        "/cd `<dir>`                  - Cambiar directorio\n"
        "/historial                   - Ver historial\n"
        "/archivos                    - Listar archivos subidos\n"
        "/subir                       - Subir `.py`\n"
        "/eliminar `<name>`           - Borrar subido\n"
        "/downloader `<URL1>` [...]   - Descargar YouTube o Telegram\n"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def execute_command(uid, cmd):
    sess = user_sessions.setdefault(uid, {"cwd": SCRIPT_DIR, "hist": []})
    try:
        if cmd.startswith("cd "):
            target = os.path.abspath(os.path.join(sess["cwd"], cmd[3:].strip()))
            if os.path.isdir(target):
                sess["cwd"] = target
                output = f"📂 Directorio cambiado a `{target}`"
            else:
                output = f"❌ El directorio `{target}` no existe"
        else:
            proc = subprocess.run(cmd, shell=True, cwd=sess["cwd"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, timeout=15)
            output = proc.stdout + proc.stderr
    except Exception as e:
        output = f"❌ Error: {e}"
    sess["hist"].append(f"$ {cmd}\n{output}")
    sess["hist"] = sess["hist"][-MAX_HISTORY_LINES:]
    return output

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
        bot.send_message(m.chat.id, "Uso: /ejecutar `<cmd>`")

@bot.message_handler(commands=['cd'])
def _cd(m):
    try:
        dirn = m.text.split(' ',1)[1]
        out = execute_command(str(m.chat.id), f"cd {dirn}")
        bot.send_message(m.chat.id, out, parse_mode='Markdown')
    except:
        bot.send_message(m.chat.id, "Uso: /cd `<dir>`")

@bot.message_handler(commands=['historial'])
def _hist(m):
    hist = user_sessions.get(str(m.chat.id), {}).get("hist", [])
    if hist:
        bot.send_message(m.chat.id, "```\n" + "\n".join(hist) + "\n```", parse_mode='Markdown')
    else:
        bot.send_message(m.chat.id, "No hay historial.")

@bot.message_handler(commands=['archivos'])
def _files(m):
    files = os.listdir(UPLOAD_FOLDER)
    if files:
        bot.send_message(m.chat.id, "```\n" + "\n".join(files) + "\n```", parse_mode='Markdown')
    else:
        bot.send_message(m.chat.id, "No hay archivos subidos.")

@bot.message_handler(content_types=['document'])
def _upload(m):
    fn = m.document.file_name
    if not fn.lower().endswith('.py'):
        return bot.send_message(m.chat.id, "Solo `.py`.")
    fp = bot.get_file(m.document.file_id).file_path
    data = bot.download_file(fp)
    dst = os.path.join(UPLOAD_FOLDER, fn)
    with open(dst, 'wb') as f:
        f.write(data)
    bot.send_message(m.chat.id, f"✅ Subido: `{fn}`", parse_mode='Markdown')

@bot.message_handler(commands=['eliminar'])
def _del(m):
    try:
        fn = m.text.split(' ',1)[1]
        path = os.path.join(UPLOAD_FOLDER, fn)
        if os.path.exists(path):
            os.remove(path)
            bot.send_message(m.chat.id, f"🗑️ Eliminado: `{fn}`", parse_mode='Markdown')
        else:
            bot.send_message(m.chat.id, "❌ No existe.")
    except:
        bot.send_message(m.chat.id, "Uso: /eliminar `<name>`")

def download_telegram_media(url: str) -> str:
    # Asegura un event loop en este hilo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    url = url.rstrip('/')
    m = re.match(r'https?://t\.me/(?:s/)?([A-Za-z0-9_]+)/(\d+)', url)
    if not m:
        raise ValueError("Enlace Telegram no soportado")
    username, msg_id = m.groups()
    msg_id = int(msg_id)

    session_name = f"session_{username}_{msg_id}"
    client = TelegramClient(session_name, API_ID, API_HASH)
    client.start(bot_token=TELEGRAM_TOKEN)
    try:
        entity = client.get_entity(username)
        message = client.get_messages(entity, ids=msg_id)
        if not message or not message.media:
            raise ValueError("Ese mensaje no contiene medios.")
        ext = message.file.ext or 'bin'
        filename = f"{username}_{msg_id}.{ext}"
        dest = os.path.join(TELEGRAM_DL_FOLDER, filename)
        client.download_media(message, file=dest)
    finally:
        client.disconnect()
        loop.close()
    return dest

@bot.message_handler(commands=['downloader'])
def _downloader(m):
    parts = m.text.split()[1:]
    if not parts:
        return bot.send_message(m.chat.id, "Uso: /downloader `<URL1>` [URL2...]")
    for url in parts:
        if 't.me/' in url:
            bot.send_message(m.chat.id, f"🔍 Descargando de Telegram:\n`{url}`", parse_mode='Markdown')
            try:
                path = download_telegram_media(url)
                bot.send_document(m.chat.id, InputFile(path), caption=os.path.basename(path))
            except Exception as e:
                bot.send_message(m.chat.id, f"❌ Error Telegram: {e}")
        else:
            bot.send_message(m.chat.id, f"🔍 Descargando de YouTube:\n`{url}`", parse_mode='Markdown')
            try:
                # limpiar previos
                for f in os.listdir(YOUTUBE_FOLDER):
                    if f.endswith('.zip'):
                        os.remove(os.path.join(YOUTUBE_FOLDER, f))
                dp = os.path.join(SCRIPT_DIR, 'downloader.py')
                res = subprocess.run([sys.executable, dp, url],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, timeout=600)
                if res.returncode != 0:
                    raise RuntimeError(res.stderr.strip())
                for z in sorted(f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip')):
                    bot.send_document(m.chat.id, InputFile(os.path.join(YOUTUBE_FOLDER, z)), caption=z)
            except Exception as e:
                bot.send_message(m.chat.id, f"❌ Error YouTube: {e}")

# Keep‑alive con Flask (compatible Render.com)
app = Flask(__name__)
@app.route('/')
def health():
    return "✅ Bot activo"

def run_bot():
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

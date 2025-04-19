#!/data/data/com.termux/files/usr/bin/env python3
import os
import sys
import subprocess
import logging
import threading
import time

import telebot
from telebot.types import InputFile
from flask import Flask

# Configuración
SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER     = os.path.join(SCRIPT_DIR, "uploads")
YOUTUBE_FOLDER    = os.path.join(SCRIPT_DIR, "youtube_downloads")
DOWNLOAD_FOLDER   = os.path.join(SCRIPT_DIR, "Telegram_Downloads")
MAX_HISTORY_LINES = 100
TELEGRAM_TOKEN    = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'
DOWNLOADER_SCRIPT = os.path.join(SCRIPT_DIR, "downloader.py")

# Asegurar carpetas
for d in (UPLOAD_FOLDER, YOUTUBE_FOLDER, DOWNLOAD_FOLDER):
    os.makedirs(d, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
session_states = {}  # chat_id → {'urls': [...], 'code': str}
user_sessions  = {}  # chat_id → {'cwd': str, 'hist': [str]}

def run_downloader(args):
    """
    Lanza downloader.py con los args dados.
    Retorna (returncode, stdout, stderr).
    """
    try:
        res = subprocess.run(
            [sys.executable, DOWNLOADER_SCRIPT] + args,
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Error: timeout al ejecutar downloader.py"

# — Comandos básicos —

@bot.message_handler(commands=["start","ayuda"])
def help_handler(m):
    msg = (
        "📥 *Bot Termux — Descargas Telegram*\n\n"
        "/start, /ayuda        - Ayuda\n"
        "/ejecutar <cmd>       - Ejecutar shell\n"
        "/cd <dir>             - Cambiar directorio\n"
        "/historial            - Historial de comandos\n"
        "/archivos             - Listar uploads\n"
        "/subir                - Subir .py/.txt/.zip\n"
        "/eliminar <archivo>   - Borrar upload\n"
        "/descargar <URL>      - Descargar YouTube\n"
        "/downloader <URLs>    - Descargar media de Telegram\n\n"
        "Ejemplo:\n"
        "`/downloader https://t.me/canal/123 https://t.me/otro/456`"
    )
    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=["ejecutar"])
def shell_exec(m):
    try:
        cmd = m.text.split(" ",1)[1]
        uid = str(m.chat.id)
        sess = user_sessions.setdefault(uid, {"cwd": SCRIPT_DIR, "hist": []})
        res = subprocess.run(
            cmd, shell=True, cwd=sess["cwd"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=15
        )
        out = res.stdout + res.stderr
        sess["hist"].append(f"$ {cmd}\n{out}")
        sess["hist"] = sess["hist"][-MAX_HISTORY_LINES:]
        bot.send_message(m.chat.id, f"```\n{out}\n```", parse_mode="Markdown")
    except:
        bot.send_message(m.chat.id, "Uso: /ejecutar <cmd>")

@bot.message_handler(commands=["cd"])
def change_dir(m):
    try:
        path = m.text.split(" ",1)[1]
        uid = str(m.chat.id)
        sess = user_sessions.setdefault(uid, {"cwd": SCRIPT_DIR, "hist": []})
        new_dir = os.path.abspath(os.path.join(sess["cwd"], path))
        if os.path.isdir(new_dir):
            sess["cwd"] = new_dir
            bot.send_message(m.chat.id, f"Directorio: {new_dir}")
        else:
            bot.send_message(m.chat.id, f"No existe: {new_dir}")
    except:
        bot.send_message(m.chat.id, "Uso: /cd <dir>")

@bot.message_handler(commands=["historial"])
def show_history(m):
    hist = user_sessions.get(str(m.chat.id), {}).get("hist", [])
    if hist:
        bot.send_message(m.chat.id, "```\n" + "\n".join(hist) + "\n```", parse_mode="Markdown")
    else:
        bot.send_message(m.chat.id, "Historial vacío")

@bot.message_handler(commands=["archivos"])
def list_uploads(m):
    files = os.listdir(UPLOAD_FOLDER)
    text = "\n".join(files) if files else "No hay archivos subidos"
    bot.send_message(m.chat.id, f"```\n{text}\n```", parse_mode="Markdown")

@bot.message_handler(commands=["subir"])
def prompt_upload(m):
    bot.send_message(m.chat.id, "Envía tu archivo (`.py`, `.txt`, `.zip`) como documento")

@bot.message_handler(content_types=["document"])
def receive_upload(m):
    fn = m.document.file_name
    if not fn.lower().endswith((".py",".txt",".zip")):
        return bot.send_message(m.chat.id, "Solo `.py`, `.txt` o `.zip`")
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
        for f in os.listdir(YOUTUBE_FOLDER):
            if f.endswith(".zip"):
                os.remove(os.path.join(YOUTUBE_FOLDER, f))
        res = subprocess.run(
            [sys.executable, DOWNLOADER_SCRIPT, url],
            cwd=SCRIPT_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=600
        )
        if res.returncode != 0:
            raise Exception(res.stderr.strip())
        for f in os.listdir(YOUTUBE_FOLDER):
            if f.endswith(".zip"):
                bot.send_document(m.chat.id, InputFile(os.path.join(YOUTUBE_FOLDER, f)))
    except:
        bot.send_message(m.chat.id, "Uso: /descargar <URL>")

# — Flujo /downloader —

@bot.message_handler(commands=["downloader"])
def downloader_start(m):
    parts = m.text.split()[1:]
    uid = str(m.chat.id)
    if not parts:
        return bot.send_message(m.chat.id, "Uso: /downloader <URL1> [URL2 ...]")
    session_states[uid] = {"urls": parts}
    ret, _, err = run_downloader(["--request-code"])
    if ret != 0:
        session_states.pop(uid, None)
        return bot.send_message(m.chat.id, f"❌ Error solicitando código:\n{err.strip()}")
    bot.send_message(m.chat.id, "📲 SMS solicitado. Envíame el código recibido.")

@bot.message_handler(func=lambda m: str(m.chat.id) in session_states and "code" not in session_states[str(m.chat.id)])
def receive_code(m):
    uid = str(m.chat.id)
    code = m.text.strip()
    if not code.isdigit():
        return bot.send_message(m.chat.id, "❌ Código inválido.")
    urls = session_states[uid]["urls"]
    session_states.pop(uid, None)
    bot.send_message(m.chat.id, f"⏳ Descargando {len(urls)} archivo(s)...")
    ret, _, err = run_downloader(["--code", code] + urls)
    if ret != 0:
        return bot.send_message(m.chat.id, f"❌ Error en descarga:\n{err.strip()}")
    files = sorted(os.listdir(DOWNLOAD_FOLDER))
    for f in files:
        bot.send_document(m.chat.id, InputFile(os.path.join(DOWNLOAD_FOLDER, f)), caption=f)

# Keep‑alive y polling
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot activo"

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

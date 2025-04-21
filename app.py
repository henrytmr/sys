#!/usr/bin/env python3
import os
import subprocess
import logging
import re
from flask import Flask, request
import telebot
from telebot.types import InputFile
from telethon.sync import TelegramClient

# ——— TUS CREDENCIALES ———
TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'
API_ID = 29246871
API_HASH = '637091dfc0eee0e2c551fd832341e18b'
APP_URL = 'https://sys-da9l.onrender.com'
PORT = int(os.environ.get('PORT', 5000))

# ——— DIRECTORIOS ———
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(SCRIPT_DIR, 'uploads')
YOUTUBE_DIR = os.path.join(SCRIPT_DIR, 'youtube_downloads')
TELEGRAM_DIR = os.path.join(SCRIPT_DIR, 'descargas_publicas')
for folder in [UPLOAD_DIR, YOUTUBE_DIR, TELEGRAM_DIR]:
    os.makedirs(folder, exist_ok=True)

# ——— INSTANCIAS ———
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)
user_sessions = {}

# ——— FUNCIONES ———
def execute_command(uid, cmd):
    sess = user_sessions.setdefault(uid, {"cwd": SCRIPT_DIR, "hist": []})
    try:
        if cmd.startswith("cd "):
            target = os.path.abspath(os.path.join(sess["cwd"], cmd[3:].strip()))
            if os.path.isdir(target):
                sess["cwd"] = target
                output = f"📂 Directorio cambiado a: `{target}`"
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
    sess["hist"] = sess["hist"][-100:]
    return output

def download_telegram_media(url: str) -> str:
    m = re.match(r'https?://t\.me/(?:s/)?([A-Za-z0-9_]+)/(\d+)', url.rstrip('/'))
    if not m:
        raise ValueError("Enlace Telegram no soportado")
    username, msg_id = m.groups()
    msg_id = int(msg_id)
    client = TelegramClient('webhook_session', API_ID, API_HASH).start(bot_token=TELEGRAM_TOKEN)
    entity = client.get_entity(username)
    message = client.get_messages(entity, ids=msg_id)
    if not message or not message.media:
        raise ValueError("Ese mensaje no contiene medios")
    ext = message.file.ext or 'bin'
    filename = f"{username}_{msg_id}.{ext}"
    path = os.path.join(TELEGRAM_DIR, filename)
    client.download_media(message, file=path)
    client.disconnect()
    return path

# ——— COMANDOS ———
@bot.message_handler(commands=['start', 'ayuda'])
def _help(m):
    bot.send_message(m.chat.id,
        "🤖 *Consola Web Bot*\n\n"
        "/ejecutar <cmd>              - Ejecutar shell\n"
        "/cd <dir>                    - Cambiar directorio\n"
        "/historial                   - Ver historial\n"
        "/archivos                    - Ver subidos\n"
        "/subir                       - Subir .py\n"
        "/eliminar <archivo>          - Eliminar archivo\n"
        "/downloader <url1> [url2..]  - Descargar Telegram o YouTube",
        parse_mode='Markdown')

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
        d = m.text.split(' ',1)[1]
        out = execute_command(str(m.chat.id), f"cd {d}")
        bot.send_message(m.chat.id, out, parse_mode='Markdown')
    except:
        bot.send_message(m.chat.id, "Uso: /cd <dir>")

@bot.message_handler(commands=['historial'])
def _hist(m):
    h = user_sessions.get(str(m.chat.id), {}).get("hist", [])
    if h:
        bot.send_message(m.chat.id, "```\n" + "\n".join(h) + "\n```", parse_mode='Markdown')
    else:
        bot.send_message(m.chat.id, "No hay historial.")

@bot.message_handler(commands=['archivos'])
def _files(m):
    files = os.listdir(UPLOAD_DIR)
    if files:
        bot.send_message(m.chat.id, "```\n" + "\n".join(files) + "\n```", parse_mode='Markdown')
    else:
        bot.send_message(m.chat.id, "No hay archivos subidos.")

@bot.message_handler(content_types=['document'])
def _upload(m):
    fn = m.document.file_name
    if not fn.lower().endswith('.py'):
        return bot.send_message(m.chat.id, "Solo se permiten .py")
    fp = bot.get_file(m.document.file_id).file_path
    data = bot.download_file(fp)
    path = os.path.join(UPLOAD_DIR, fn)
    with open(path, 'wb') as f: f.write(data)
    bot.send_message(m.chat.id, f"✅ Subido: `{fn}`", parse_mode='Markdown')

@bot.message_handler(commands=['eliminar'])
def _delete(m):
    try:
        fn = m.text.split(' ',1)[1]
        p = os.path.join(UPLOAD_DIR, fn)
        if os.path.exists(p):
            os.remove(p)
            bot.send_message(m.chat.id, f"🗑️ Eliminado: `{fn}`", parse_mode='Markdown')
        else:
            bot.send_message(m.chat.id, "❌ No existe.")
    except:
        bot.send_message(m.chat.id, "Uso: /eliminar <archivo>")

@bot.message_handler(commands=['downloader'])
def _downloader(m):
    urls = m.text.split()[1:]
    if not urls:
        return bot.send_message(m.chat.id, "Uso: /downloader <URL>")
    for url in urls:
        if 't.me/' in url:
            bot.send_message(m.chat.id, f"🔍 Telegram: `{url}`", parse_mode='Markdown')
            try:
                path = download_telegram_media(url)
                bot.send_document(m.chat.id, InputFile(path))
            except Exception as e:
                bot.send_message(m.chat.id, f"❌ Error Telegram: {e}")
        else:
            bot.send_message(m.chat.id, f"🔍 YouTube: `{url}`", parse_mode='Markdown')
            try:
                for f in os.listdir(YOUTUBE_DIR):
                    if f.endswith('.zip'):
                        os.remove(os.path.join(YOUTUBE_DIR, f))
                dp = os.path.join(SCRIPT_DIR, 'downloader.py')
                res = subprocess.run(['python3', dp, url], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode:
                    raise Exception(res.stderr.strip())
                for f in os.listdir(YOUTUBE_DIR):
                    if f.endswith('.zip'):
                        bot.send_document(m.chat.id, InputFile(os.path.join(YOUTUBE_DIR, f)))
            except Exception as e:
                bot.send_message(m.chat.id, f"❌ Error YouTube: {e}")

# ——— FLASK ENDPOINTS ———
@app.route('/')
def health(): return "Bot OK", 200

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.data.decode("utf-8"))
    bot.process_new_updates([update])
    return '', 200

# ——— MAIN ———
if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=f"{APP_URL}/{TELEGRAM_TOKEN}")
    app.run(host="0.0.0.0", port=PORT)

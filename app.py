import os
from flask import Flask, request
import telebot
from telebot.types import InputFile
import subprocess
import re
from telethon.sync import TelegramClient
from telethon.errors import ChannelPrivateError

# ——— Configuración ———
TOKEN       = os.environ['6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU']
API_ID      = int(os.environ['29246871'])
API_HASH    = os.environ['637091dfc0eee0e2c551fd832341e18b']
APP_URL     = os.environ['https://sys-da9l.onrender.com/'].rstrip('/')  # e.g. https://mi-app.onrender.com

UPLOAD_DIR      = 'uploads'
YOUTUBE_DIR     = 'youtube_downloads'
TELEGRAM_DIR    = 'descargas_publicas'
for d in (UPLOAD_DIR, YOUTUBE_DIR, TELEGRAM_DIR):
    os.makedirs(d, exist_ok=True)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

def download_telegram_media(url: str) -> str:
    """
    Descarga un medio de Telegram público desde t.me/<user>/<msg_id>
    de forma síncrona usando Telethon.
    """
    url = url.rstrip('/')
    m = re.match(r'https?://t\.me/(?:s/)?([A-Za-z0-9_]+)/(\d+)', url)
    if not m:
        raise ValueError("Enlace Telegram no soportado")
    username, msg_id = m.groups()
    msg_id = int(msg_id)
    client = TelegramClient('tmp', API_ID, API_HASH).start(bot_token=TOKEN)
    entity = client.get_entity(username)
    message = client.get_messages(entity, ids=msg_id)
    if not message or not message.media:
        raise ValueError("Ese mensaje no contiene medios")
    ext = message.file.ext or 'bin'
    fn = f"{username}_{msg_id}.{ext}"
    path = os.path.join(TELEGRAM_DIR, fn)
    client.download_media(message, file=path)
    client.disconnect()
    return path

@bot.message_handler(commands=['start', 'ayuda'])
def help_handler(msg):
    text = (
        "🤖 *Consola Web Bot*\n\n"
        "/downloader `<URL>`  - YouTube o Telegram\n"
        "/resto de comandos…"
    )
    bot.send_message(msg.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['downloader'])
def dl_handler(msg):
    parts = msg.text.split()[1:]
    if not parts:
        return bot.send_message(msg.chat.id, "Uso: /downloader `<URL>`")
    for url in parts:
        if 't.me/' in url:
            bot.send_message(msg.chat.id, f"🔍 Telegram: `{url}`", parse_mode='Markdown')
            try:
                path = download_telegram_media(url)
                bot.send_document(msg.chat.id, InputFile(path))
            except Exception as e:
                bot.send_message(msg.chat.id, f"❌ Error Telegram: {e}")
        else:
            bot.send_message(msg.chat.id, f"🔍 YouTube: `{url}`", parse_mode='Markdown')
            # Llama a tu downloader.py existente
            res = subprocess.run(
                ['python3', 'downloader.py', url],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if res.returncode:
                bot.send_message(msg.chat.id, f"❌ Error YouTube: {res.stderr}")
            else:
                # Envía los archivos .zip generados
                for f in sorted(os.listdir(YOUTUBE_DIR)):
                    if f.endswith('.zip'):
                        bot.send_document(msg.chat.id, InputFile(os.path.join(YOUTUBE_DIR, f)))

# Health check para Render
@app.route('/')
def health():
    return 'OK', 200

# Webhook: recibe actualizaciones de Telegram
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode(), bot)
    bot.process_new_updates([update])
    return '', 200

if __name__ == '__main__':
    # Configurar webhook en Telegram
    bot.remove_webhook()  # limpia posibles webhooks previos
    bot.set_webhook(url=f"{APP_URL}/{TOKEN}")  # registra el nuevo
    # Iniciar Flask; en producción usar gunicorn
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

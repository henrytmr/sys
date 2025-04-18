import os
import sys
import subprocess
import logging
import threading
import telebot
import tempfile
import time
from telebot.types import InputFile
from flask import Flask

# Configuración
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER    = os.path.join(SCRIPT_DIR, "uploads")
YOUTUBE_FOLDER   = os.path.join(SCRIPT_DIR, "youtube_downloads")
MAX_HISTORY_LINES= 100
TELEGRAM_TOKEN   = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'

# Asegurar carpetas
os.makedirs(UPLOAD_FOLDER,  exist_ok=True)
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Estado por usuario
bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}

def send_help(message):
    text = (
        "Consola Web Bot\n\n"
        "/start, /ayuda         - Mostrar ayuda\n"
        "/ejecutar <cmd>        - Ejecutar en shell\n"
        "/cd <dir>              - Cambiar directorio\n"
        "/historial             - Ver historial\n"
        "/archivos              - Listar subidos\n"
        "/subir                 - Subir .py\n"
        "/eliminar <name>       - Borrar archivo\n"
        "/descargar <URL>       - Descargar YouTube"
    )
    bot.send_message(message.chat.id, text)

def execute_command(uid, cmd):
    sess = user_sessions.setdefault(uid, {"cwd":SCRIPT_DIR, "hist":[]})
    output = ""
    try:
        if cmd.startswith("cd "):
            path = cmd[3:].strip()
            new = os.path.abspath(os.path.join(sess["cwd"], path))
            if os.path.isdir(new):
                sess["cwd"] = new
                output = f"Directorio: {new}"
            else:
                output = f"Error: {new} no existe"
        else:
            res = subprocess.run(cmd, shell=True, cwd=sess["cwd"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            output = res.stdout + res.stderr
    except Exception as e:
        output = f"Error: {e}"
    sess["hist"].append(f"$ {cmd}\n{output}")
    sess["hist"] = sess["hist"][-MAX_HISTORY_LINES:]
    return output

@bot.message_handler(commands=['start','ayuda'])
def _start(m): send_help(m)

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
    hist = user_sessions.get(str(m.chat.id),{}).get("hist",[])
    if hist:
        bot.send_message(m.chat.id, "```\n" + "\n".join(hist) + "\n```", parse_mode='Markdown')
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
        return bot.send_message(m.chat.id, "Solo .py")
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

@bot.message_handler(commands=['descargar'])
def _dl(m):
    try:
        url = m.text.split(' ',1)[1]
        # limpiar previos
        for f in os.listdir(YOUTUBE_FOLDER):
            if f.endswith('.zip'):
                os.remove(os.path.join(YOUTUBE_FOLDER,f))
        # llamar downloader.py
        dp = os.path.join(SCRIPT_DIR,'downloader.py')
        res = subprocess.run([sys.executable, dp, url],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
        if res.returncode!=0:
            raise Exception(res.stderr.strip())
        # enviar partes
        parts = sorted(f for f in os.listdir(YOUTUBE_FOLDER) if f.endswith('.zip'))
        for p in parts:
            bot.send_document(m.chat.id, InputFile(os.path.join(YOUTUBE_FOLDER,p)), caption=p)
    except:
        bot.send_message(m.chat.id, "Uso: /descargar <URL>")

# Flask para keep-alive
app = Flask(__name__)
@app.route('/')
def home(): return "Bot activo"

def run_bot():
    while True:
        try: bot.infinity_polling()
        except Exception as e:
            logger.error(e)
            time.sleep(5)

threading.Thread(target=run_bot, daemon=True).start()

if __name__=="__main__":
    app.run(host='0.0.0.0', port=5000)

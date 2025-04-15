import os
import subprocess
import uuid
import shlex
import logging
import threading
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
import telebot
from telebot.types import InputFile

# Configuración general
UPLOAD_FOLDER = os.path.abspath("uploads")
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100
TELEGRAM_TOKEN = "6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU"

# Inicializar Flask
app = Flask("consola_web")
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SESSION_TYPE"] = "filesystem"
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB
Session(app)

# Inicializar Telegram Bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Estructuras de datos
user_sessions = {}
telegram_sessions = {}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Funciones comunes
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

def execute_command(session_id, command):
    user = user_sessions[session_id]
    output = ""
    
    try:
        if command.startswith("cd "):
            new_dir = command[3:].strip()
            target = os.path.join(user["cwd"], new_dir)
            os.chdir(target)
            user["cwd"] = os.getcwd()
            output = f"Directorio actual: {user['cwd']}"
        else:
            process = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=user["cwd"]
            )
            stdout, stderr = process.communicate(timeout=15)
            output = stdout + stderr
            if process.returncode != 0:
                output += f"\n[Código salida: {process.returncode}]"
                
    except Exception as e:
        output = f"Error: {str(e)}"
    
    user["history"].append(f"$ {command}\n{output}")
    user["history"] = clean_history(user["history"])
    return output

# Handlers de Telegram
@bot.message_handler(commands=['start', 'ayuda'])
def send_help(message):
    help_text = """
🖥️ *Consola Web Bot* 🖥️

Comandos disponibles:
/start - Iniciar el bot
/ayuda - Mostrar esta ayuda
/ejecutar <comando> - Ejecutar comando en la terminal
/archivos - Listar archivos subidos
/subir - Subir archivo .py (envía el archivo como documento)
/eliminar <nombre> - Eliminar archivo
/cd <directorio> - Cambiar directorio
/historial - Mostrar últimos comandos
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['ejecutar'])
def handle_execute(message):
    try:
        command = message.text.split(' ', 1)[1]
        session_id = str(message.chat.id)
        
        if session_id not in telegram_sessions:
            telegram_sessions[session_id] = {
                "history": [],
                "cwd": os.getcwd()
            }
            user_sessions[session_id] = telegram_sessions[session_id]
            
        output = execute_command(session_id, command)
        bot.send_message(message.chat.id, f"```\n{output}\n```", parse_mode='Markdown')
        
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /ejecutar <comando>")

@bot.message_handler(commands=['archivos'])
def list_files(message):
    files = os.listdir(UPLOAD_FOLDER)
    response = "📁 *Archivos subidos:*\n" + "\n".join(files) if files else "No hay archivos subidos"
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

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
            
        bot.reply_to(message, f"✅ Archivo *{filename}* subido correctamente", parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['eliminar'])
def handle_delete(message):
    try:
        filename = message.text.split(' ', 1)[1]
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        
        if not os.path.exists(filepath):
            raise FileNotFoundError("Archivo no encontrado")
            
        os.remove(filepath)
        bot.send_message(message.chat.id, f"🗑️ Archivo *{filename}* eliminado", parse_mode='Markdown')
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['cd'])
def handle_cd(message):
    try:
        directory = message.text.split(' ', 1)[1]
        session_id = str(message.chat.id)
        
        if session_id not in telegram_sessions:
            telegram_sessions[session_id] = {
                "history": [],
                "cwd": os.getcwd()
            }
            
        user = telegram_sessions[session_id]
        new_dir = os.path.join(user["cwd"], directory)
        os.chdir(new_dir)
        user["cwd"] = os.getcwd()
        bot.send_message(message.chat.id, f"📂 Directorio actual: `{user['cwd']}`", parse_mode='Markdown')
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['historial'])
def show_history(message):
    session_id = str(message.chat.id)
    if session_id in telegram_sessions:
        history = "\n".join(telegram_sessions[session_id]["history"][-5:])
        bot.send_message(message.chat.id, f"📜 *Últimos comandos:*\n```\n{history}\n```", parse_mode='Markdown')
    else:
        bot.send_message(message.chat.id, "No hay historial disponible")

# Rutas de Flask (mantenidas desde la versión original)
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return render_template("error.html", error=f"{e.code} - {e.name}"), e.code

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Error: {str(e)}")
    return render_template("error.html", error=f"Error interno: {str(e)}"), 500

@app.route("/", methods=["GET"])
def index():
    # ... (mantener código original de Flask)

@app.route("/execute", methods=["POST"])
def execute():
    # ... (mantener código original de Flask)

@app.route("/upload", methods=["POST"])
def upload_file():
    # ... (mantener código original de Flask)

@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    # ... (mantener código original de Flask)

# Iniciar el bot de Telegram en un hilo separado
def run_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=5000)
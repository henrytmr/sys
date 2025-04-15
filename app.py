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

# Configuraci車n
UPLOAD_FOLDER = os.path.abspath("uploads")
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '')

# Inicializar Flask
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta_default")
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
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            "history": [],
            "cwd": os.getcwd()
        }
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
                output += f"\n[C車digo salida: {process.returncode}]"
    except Exception as e:
        output = f"Error: {str(e)}"
    user["history"].append(f"$ {command}\n{output}")
    user["history"] = clean_history(user["history"])
    return output

# Handlers de Telegram
@bot.message_handler(commands=['start', 'ayuda'])
def send_help(message):
    help_text = """
Consola Web Bot

Comandos disponibles:
/start - Iniciar el bot
/ayuda - Mostrar esta ayuda
/ejecutar <comando> - Ejecutar comando en la terminal
/archivos - Listar archivos subidos
/subir - Subir archivo .py (env赤a el archivo como documento)
/eliminar <nombre> - Eliminar archivo
/cd <directorio> - Cambiar directorio
/historial - Mostrar 迆ltimos comandos
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['ejecutar'])
def handle_execute(message):
    try:
        command = message.text.split(' ', 1)[1]
        session_id = str(message.chat.id)
        output = execute_command(session_id, command)
        bot.send_message(message.chat.id, f"```\n{output}\n```", parse_mode='Markdown')
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /ejecutar <comando>")

@bot.message_handler(commands=['archivos'])
def list_files(message):
    files = os.listdir(UPLOAD_FOLDER)
    response = "Archivos subidos:\n" + "\n".join(files) if files else "No hay archivos subidos"
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
        bot.reply_to(message, f"Archivo {filename} subido correctamente", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

# Rutas de Flask
@app.route("/", methods=["GET"])
def index():
    try:
        if "session_id" not in session:
            session_id = str(uuid.uuid4())
            session["session_id"] = session_id
            user_sessions[session_id] = {"history": [], "cwd": os.getcwd()}
        files = os.listdir(UPLOAD_FOLDER)
        return render_template("index.html", files=files)
    except Exception as e:
        logging.error(f"Error en index: {str(e)}")
        return render_template("error.html", error=f"Error inicial: {str(e)}"), 500

@app.route("/execute", methods=["POST"])
def execute():
    try:
        session_id = session.get("session_id")
        if not session_id or session_id not in user_sessions:
            return jsonify({"error": "Sesi車n inv芍lida"}), 401
        data = request.get_json()
        command = data.get("command", "").strip()
        if not command:
            return jsonify({
                "output": "",
                "history": user_sessions[session_id]["history"],
                "cwd": user_sessions[session_id]["cwd"]
            })
        output = execute_command(session_id, command)
        return jsonify({
            "output": output,
            "history": user_sessions[session_id]["history"],
            "cwd": user_sessions[session_id]["cwd"]
        })
    except Exception as e:
        logging.error(f"Error execute: {str(e)}")
        return jsonify({"error": "Error interno"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se encontr車 el archivo'}), 400
        file = request.files['archivo']
        if file.filename == '':
            return jsonify({'error': 'No se seleccion車 archivo'}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return jsonify({'success': f'Archivo {filename} subido correctamente'})
        return jsonify({'error': 'Solo se permiten archivos .py'}), 400
    except Exception as e:
        logging.error(f"Error en upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if not os.path.exists(filepath):
            return jsonify({'error': 'Archivo no encontrado'}), 404
        os.remove(filepath)
        return jsonify({'success': f'Archivo {filename} eliminado'})
    except Exception as e:
        logging.error(f"Error en delete: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Iniciar el bot de Telegram solo si se configura RUN_BOT como true (variable de entorno)
if os.environ.get("RUN_BOT", "false") == "true":
    threading.Thread(target=bot.infinity_polling, daemon=True).start()

def create_app():
    return app

if __name__ == "__main__":
    # Para ejecuci車n local
    app.run(host='0.0.0.0', port=5000)
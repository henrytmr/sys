import os
import subprocess
import shlex
import logging
import telebot
from telebot.types import InputFile
from werkzeug.utils import secure_filename

# Configuración
UPLOAD_FOLDER = os.path.abspath("uploads")
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100

# Token incluido directamente
TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_sessions = {}  # Se utilizará el chat ID para guardar sesión: historial y cwd

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

def execute_command(session_id, command):
    if session_id not in user_sessions:
        user_sessions[session_id] = {"history": [], "cwd": os.getcwd()}
    session_info = user_sessions[session_id]
    output = ""
    try:
        if command.startswith("cd "):
            new_dir = command[3:].strip()
            target = os.path.join(session_info["cwd"], new_dir)
            os.chdir(target)
            session_info["cwd"] = os.getcwd()
            output = "Directorio actual: " + session_info["cwd"]
        else:
            process = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=session_info["cwd"]
            )
            stdout, stderr = process.communicate(timeout=15)
            output = stdout + stderr
            if process.returncode != 0:
                output += f"\n[Código salida: {process.returncode}]"
    except Exception as e:
        output = f"Error: {str(e)}"
    session_info["history"].append(f"$ {command}\n{output}")
    session_info["history"] = clean_history(session_info["history"])
    return output

# Handlers de Telegram

@bot.message_handler(commands=['start', 'ayuda'])
def send_help(message):
    help_text = (
        "Consola Web Bot\n\n"
        "Comandos disponibles:\n"
        "/start - Iniciar el bot\n"
        "/ayuda - Mostrar esta ayuda\n"
        "/ejecutar <comando> - Ejecutar comando en la terminal\n"
        "/archivos - Listar archivos subidos\n"
        "/subir - Subir archivo .py (envía el archivo como documento)\n"
        "/eliminar <nombre> - Eliminar archivo\n"
        "/cd <directorio> - Cambiar directorio\n"
        "/historial - Mostrar últimos comandos\n"
    )
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['ejecutar'])
def handle_execute(message):
    try:
        command = message.text.split(' ', 1)[1]
        session_id = str(message.chat.id)
        output = execute_command(session_id, command)
        bot.send_message(message.chat.id, "```\n" + output + "\n```", parse_mode='Markdown')
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /ejecutar <comando>")

@bot.message_handler(commands=['archivos'])
def list_files(message):
    files = os.listdir(UPLOAD_FOLDER)
    response = "Archivos subidos:\n" + "\n".join(files) if files else "No hay archivos subidos"
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['historial'])
def show_history(message):
    session_id = str(message.chat.id)
    if session_id in user_sessions:
        history = "\n".join(user_sessions[session_id]["history"])
        bot.send_message(message.chat.id, "Historial:\n" + history)
    else:
        bot.send_message(message.chat.id, "No hay historial aún.")

@bot.message_handler(commands=['eliminar'])
def delete_file(message):
    try:
        filename = message.text.split(' ', 1)[1]
        filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            bot.send_message(message.chat.id, f"Archivo {filename} eliminado.")
        else:
            bot.send_message(message.chat.id, "Archivo no encontrado.")
    except IndexError:
        bot.send_message(message.chat.id, "Uso: /eliminar <nombre>")

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
        bot.reply_to(message, f"Archivo {filename} subido correctamente.")
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

if __name__ == '__main__':
    bot.infinity_polling()
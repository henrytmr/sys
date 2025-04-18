import os import subprocess import shlex import logging import threading import telebot import shutil import tempfile import time from telebot.types import InputFile from werkzeug.utils import secure_filename from flask import Flask

Configuración

UPLOAD_FOLDER = os.path.abspath("uploads") YOUTUBE_FOLDER = os.path.abspath("youtube_downloads") ALLOWED_EXTENSIONS = {'py'} MAX_HISTORY_LINES = 100 TELEGRAM_TOKEN = '6998654254:AAG-6_xNjBI0fAfa5v8iMLA4o0KDwkmy_JU'

Ruta absoluta al archivo cookies.txt en la carpeta del script

SCRIPT_DIR = os.path.dirname(os.path.abspath(file)) COOKIE_FILE = os.path.join(SCRIPT_DIR, 'cookies.txt')

Asegurar directorios

os.makedirs(UPLOAD_FOLDER, exist_ok=True) os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

Inicializar bot y sesiones de usuario

bot = telebot.TeleBot(TELEGRAM_TOKEN) user_sessions = {}

def allowed_file(filename): return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_history(history): return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

def execute_command(session_id, command): if session_id not in user_sessions: user_sessions[session_id] = { "history": [], "cwd": os.getcwd(), "base_dir": os.getcwd() }

session_info = user_sessions[session_id]
output = ""

try:
    if command.startswith("cd "):
        parts = shlex.split(command, posix=True)
        if len(parts) < 2:
            raise ValueError("Directorio no especificado")

        new_dir = ' '.join(parts[1:])
        new_dir = os.path.normpath(new_dir)

        if os.path.isabs(new_dir):
            target = os.path.abspath(os.path.join(session_info["base_dir"], new_dir.lstrip('/')))
        else:
            target = os.path.abspath(os.path.join(session_info["cwd"], new_dir))

        if not target.startswith(session_info["base_dir"]):
            raise ValueError("Acceso a directorio no permitido")

        if not os.path.isdir(target):
            raise FileNotFoundError(f"Directorio no encontrado: {target}")

        session_info["cwd"] = target
        output = f"Directorio actual: {session_info['cwd']}"

    else:
        args = shlex.split(command, posix=True)
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=session_info["cwd"]
        )
        stdout, stderr = proc.communicate(timeout=15)
        output = stdout + stderr
        if proc.returncode != 0:
            output += f"\n[Código salida: {proc.returncode}]"

except Exception as e:
    output = f"Error: {str(e)}"

session_info["history"].append(f"$ {command}\n{output}")
session_info["history"] = clean_history(session_info["history"])
return output

@bot.message_handler(commands=['start', 'ayuda']) def send_help(message): help_text = ( "Consola Web Bot\n\n" "Comandos disponibles:\n" "/start, /ayuda         - Mostrar ayuda\n" "/ejecutar <comando>    - Ejecutar comando en la terminal\n" "/cd <directorio>       - Cambiar directorio\n" "/historial             - Mostrar últimos comandos\n" "/archivos              - Listar archivos subidos\n" "/subir                 - Subir archivo .py (envía el archivo)\n" "/eliminar <nombre>     - Eliminar archivo subido\n" "/descargar <URL>       - Descargar video de YouTube en partes ZIP\n" ) bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['ejecutar']) def handle_execute(message): try: cmd = message.text.split(maxsplit=1)[1] out = execute_command(str(message.chat.id), cmd) bot.send_message(message.chat.id, f"\n{out}\n", parse_mode='Markdown') except IndexError: bot.send_message(message.chat.id, "Uso: /ejecutar <comando>") except Exception as e: bot.send_message(message.chat.id, f"Error crítico: {str(e)}")

@bot.message_handler(commands=['cd']) def change_dir(message): try: path = message.text.split(maxsplit=1)[1] out = execute_command(str(message.chat.id), f"cd {path}") bot.send_message(message.chat.id, out) except IndexError: bot.send_message(message.chat.id, "Uso: /cd <directorio>")

@bot.message_handler(commands=['historial']) def show_history(message): session_id = str(message.chat.id) if session_id in user_sessions and user_sessions[session_id]["history"]: history = "\n".join(user_sessions[session_id]["history"]) bot.send_message(message.chat.id, f"\n{history}\n", parse_mode='Markdown') else: bot.send_message(message.chat.id, "No hay historial de comandos")

@bot.message_handler(commands=['archivos']) def list_files(message): try: files = os.listdir(UPLOAD_FOLDER) if files: file_list = "\n".join(files) bot.send_message(message.chat.id, f"Archivos subidos:\n\n{file_list}\n", parse_mode='Markdown') else: bot.send_message(message.chat.id, "No hay archivos subidos") except Exception as e: bot.send_message(message.chat.id, f"Error al listar archivos: {str(e)}")

@bot.message_handler(content_types=['document']) def handle_file(message): if not allowed_file(message.document.file_name): bot.send_message(message.chat.id, "Solo se permiten archivos .py") return

try:
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    filename = secure_filename(message.document.file_name)
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    with open(filepath, 'wb') as new_file:
        new_file.write(downloaded_file)

    bot.send_message(message.chat.id, f"Archivo {filename} subido correctamente")
except Exception as e:
    bot.send_message(message.chat.id, f"Error al subir archivo: {str(e)}")

@bot.message_handler(commands=['eliminar']) def delete_file(message): try: filename = message.text.split(maxsplit=1)[1] filename = secure_filename(filename) filepath = os.path.join(UPLOAD_FOLDER, filename)

if os.path.exists(filepath):
        os.remove(filepath)
        bot.send_message(message.chat.id, f"Archivo {filename} eliminado")
    else:
        bot.send_message(message.chat.id, f"Archivo {filename} no encontrado")
except IndexError:
    bot.send_message(message.chat.id, "Uso: /eliminar <nombre_archivo>")
except Exception as e:
    bot.send_message(message.chat.id, f"Error al eliminar archivo: {str(e)}")

@bot.message_handler(commands=['descargar']) def download_youtube(message): try: url = message.text.split(maxsplit=1)[1].split('?')[0]  # Limpiar parámetros de URL

# Configuración especial para Render
    env = os.environ.copy()
    env["PATH"] = f"/opt/render/project/src/bin:{env['PATH']}"
    env["FFMPEG_PATH"] = "/opt/render/project/src/bin/ffmpeg"
    env["FFPROBE_PATH"] = "/opt/render/project/src/bin/ffprobe"

    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = [
            'yt-dlp',
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            '-o', f'{temp_dir}/%(title)s.%(ext)s',
            '--ffmpeg-location', '/opt/render/project/src/bin',
        ]

        # Incluir cookies si existe el archivo
        if os.path.isfile(COOKIE_FILE):
            cmd.extend(['--cookies', COOKIE_FILE])

        cmd.append(url)

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=300
        )

        if result.returncode != 0:
            raise Exception(f"Error yt-dlp: {result.stderr}")

        files = os.listdir(temp_dir)
        if not files:
            raise ValueError("No se generó archivo de video")

        downloaded_file = files[0]
        zip_path = os.path.join(YOUTUBE_FOLDER, f"{downloaded_file}.zip")
        shutil.make_archive(os.path.splitext(zip_path)[0], 'zip', temp_dir)

        with open(zip_path, 'rb') as f:
            bot.send_document(message.chat.id, InputFile(f))

except IndexError:
    bot.send_message(message.chat.id, "Uso: /descargar <URL>")
except Exception as e:
    bot.send_message(message.chat.id, f"Error al descargar: {str(e)}")

app = Flask(name)

@app.route('/') def index(): return "Telegram Bot en ejecución"

def start_bot(): while True: try: bot.infinity_polling() except Exception as e: logging.error(f"Error en polling: {str(e)}") time.sleep(5)

threading.Thread(target=start_bot, daemon=True).start()

if name == 'main': app.run(host='0.0.0.0', port=5000)


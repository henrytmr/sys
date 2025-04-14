import os
import subprocess
import uuid
import shlex
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

# Configuración
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'py'}
MAX_HISTORY_LINES = 100

app = Flask("consola_web")
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SESSION_TYPE"] = "filesystem"
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB
Session(app)

# Logging
logging.basicConfig(level=logging.INFO)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
user_sessions = {}

# Manejo de errores
@app.errorhandler(HTTPException)
def handle_http_exception(e):
    return render_template("error.html", error=f"{e.code} - {e.name}"), e.code

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Error: {str(e)}")
    return render_template("error.html", error=f"Error interno: {str(e)}"), 500

# Funciones auxiliares
def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

# Rutas
@app.route("/", methods=["GET"])
def index():
    try:
        if "session_id" not in session:
            session_id = str(uuid.uuid4())
            session["session_id"] = session_id
            user_sessions[session_id] = {
                "history": [],
                "cwd": os.getcwd()
            }
        
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
            return jsonify({"error": "Sesión inválida"}), 401
            
        data = request.get_json()
        command = data.get("command", "").strip()
        user = user_sessions[session_id]

        if not command:
            return jsonify({"output": "", "history": user["history"], "cwd": user["cwd"]})
        
        if command == "clear":
            user["history"] = []
            return jsonify({"output": "", "history": user["history"], "cwd": user["cwd"]})
        
        output = ""
        try:
            if command.startswith("cd "):
                new_dir = command[3:].strip()
                target = os.path.join(user["cwd"], new_dir)
                os.chdir(target)
                user["cwd"] = os.getcwd()
                output = f"Directorio: {user['cwd']}"
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
        return jsonify({
            "output": output, 
            "history": user["history"],
            "cwd": user["cwd"]
        })
        
    except Exception as e:
        logging.error(f"Error execute: {str(e)}")
        return jsonify({"error": "Error interno"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        file = request.files['archivo']
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'success': f'Archivo {filename} subido'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        os.remove(filepath)
        return jsonify({'success': f'Archivo {filename} eliminado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
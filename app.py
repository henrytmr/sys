import os
import subprocess
import uuid
import shlex
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename

app = Flask("consola_web")
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
user_sessions = {}

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
        
        files = os.listdir(app.config['UPLOAD_FOLDER'])
        return render_template("index.html", files=files)
    except Exception as e:
        logging.error(f"Error inicial: {str(e)}")
        return render_template("error.html", error="Error inicializando sesión")

@app.route("/execute", methods=["POST"])
def execute():
    try:
        session_id = session.get("session_id")
        if not session_id or session_id not in user_sessions:
            return jsonify({"error": "Sesión no válida"}), 401
            
        data = request.get_json()
        command = data.get("command", "").strip()
        user = user_sessions[session_id]

        if not command:
            return jsonify({"output": "", "history": user["history"]})
        
        if command == "clear":
            user["history"] = []
            return jsonify({"output": "", "history": user["history"]})
        
        try:
            process = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=user.get("cwd", os.getcwd())
            )
            
            stdout, stderr = process.communicate()
            output = stdout + stderr
            
            if process.returncode != 0:
                output += f"\n[Código de salida: {process.returncode}]"
            
        except Exception as e:
            output = f"Error: {str(e)}"
        
        user["history"].append(f"$ {command}\n{output}")
        return jsonify({"output": output, "history": user["history"]})
        
    except Exception as e:
        logging.error(f"Error en execute: {str(e)}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        file = request.files['archivo']
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'success': f'Archivo {filename} subido correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    try:
        safe_filename = secure_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        os.remove(filepath)
        return jsonify({'success': f'Archivo {safe_filename} eliminado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/run/<filename>", methods=["POST"])
def run_file(filename):
    try:
        safe_filename = secure_filename(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        process = subprocess.Popen(
            ['python3', filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        output = stdout + stderr
        return jsonify({'output': output})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
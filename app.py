import os
import subprocess
import uuid
import shlex
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename

# Configuración
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'py'}

app = Flask("consola_web")
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Logging
logging.basicConfig(
    filename='app.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
user_sessions = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    try:
        if "session_id" not in session:
            session["session_id"] = str(uuid.uuid4())
            user_sessions[session["session_id"]] = {
                "globals": {},
                "history": [],
                "cwd": os.getcwd()
            }
        files = os.listdir(UPLOAD_FOLDER)
        return render_template("index.html", output="", files=files)
    except Exception as e:
        logging.error(f"Index error: {str(e)}")
        return render_template("index.html", output=f"Error: {str(e)}", files=[])

@app.route("/execute", methods=["POST"])
def execute():
    try:
        data = request.get_json()
        command = data.get("command", "").strip()
        
        if not command:
            return jsonify({"output": "", "history": []})
        
        user = user_sessions[session["session_id"]]
        
        if command.lower() == "clear":
            user["history"] = []
            return jsonify({"output": "", "history": []})
        
        if command.lower() == "dir":
            command = "ls -l"
        
        try:
            if command.startswith("cd "):
                new_dir = command[3:].strip()
                os.chdir(new_dir)
                user["cwd"] = os.getcwd()
                output = f"Directorio actual: {user['cwd']}"
            else:
                result = subprocess.run(
                    shlex.split(command),
                    capture_output=True,
                    text=True,
                    cwd=user.get("cwd", os.getcwd())
                )
                output = result.stdout + result.stderr
                
        except Exception as e:
            output = f"Error: {str(e)}"
        
        user["history"].append({"command": command, "output": output})
        return jsonify({"output": output, "history": user["history"]})
        
    except Exception as e:
        logging.error(f"Execute error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se seleccionó archivo'}), 400
            
        file = request.files['archivo']
        if file.filename == '':
            return jsonify({'error': 'Nombre vacío'}), 400
        
        if not (file and allowed_file(file.filename)):
            return jsonify({'error': 'Solo archivos .py'}), 400
            
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if os.path.exists(filepath):
            return jsonify({'error': 'El archivo ya existe'}), 409
            
        file.save(filepath)
        return jsonify({'success': f'{filename} subido correctamente'})
        
    except Exception as e:
        logging.error(f"Upload error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route("/run/<filename>")
def run_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if not os.path.exists(filepath):
            return jsonify({'error': 'Archivo no encontrado'}), 404
            
        result = subprocess.run(
            ['python3', filepath],
            capture_output=True,
            text=True
        )
        output = result.stdout + result.stderr
        
        if "session_id" in session:
            user = user_sessions.get(session["session_id"])
            if user:
                user["history"].append({"command": f"python {filename}", "output": output})
        
        return jsonify({'output': output})
        
    except Exception as e:
        logging.error(f"Run error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route("/delete/<filename>", methods=["DELETE"])
def delete_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': f'{filename} eliminado correctamente'})
        return jsonify({'error': 'Archivo no encontrado'}), 404
        
    except Exception as e:
        logging.error(f"Delete error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Iniciar servidor
app.run(host='0.0.0.0', port=5000)
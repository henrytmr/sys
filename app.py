import os
import subprocess
import uuid
import shlex
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'py'}

app = Flask("consola_web")
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SESSION_TYPE"] = "filesystem"
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB máximo
Session(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
user_sessions = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET"])
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        user_sessions[session["session_id"]] = {
            "globals": {},
            "history": [],
            "mode": "bash",
            "cwd": os.getcwd()
        }
    files = os.listdir(UPLOAD_FOLDER)
    return render_template("index.html", output="", files=files)

@app.route("/execute", methods=["POST"])
def execute():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        user_sessions[session["session_id"]] = {
            "globals": {},
            "history": [],
            "mode": "bash",
            "cwd": os.getcwd()
        }
    data = request.get_json()
    command = data.get("command", "").strip()
    mode = data.get("mode", "bash")
    user = user_sessions[session["session_id"]]
    user["mode"] = mode

    if not command:
        return jsonify({"output": "", "history": user["history"]})
    if command == "clear":
        user["history"] = []
        return jsonify({"output": "", "history": user["history"]})
    
    try:
        if mode == "bash":
            if command.startswith("cd "):
                new_dir = command[3:].strip()
                try:
                    os.chdir(new_dir)
                    user["cwd"] = os.getcwd()
                    output = f"Directorio cambiado a: {user['cwd']}"
                except Exception as e:
                    output = f"Error: {str(e)}"
            else:
                result = subprocess.run(
                    shlex.split(command),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=user.get("cwd", os.getcwd())
                )
                output = result.stdout + result.stderr
        elif mode == "python":
            local_ctx = user["globals"]
            exec(command, local_ctx)
            output = local_ctx.get("_", "") or "Comando ejecutado."
        else:
            output = "Modo inválido."
    except Exception as e:
        output = f"Error: {e}"
    
    user["history"].append(f"$ {command}\n{output}")
    return jsonify({"output": output, "history": user["history"]})

@app.route("/upload", methods=["POST"])
def upload_file():
    if 'archivo' not in request.files:
        return jsonify({'error': 'No se seleccionó archivo'}), 400
    
    file = request.files['archivo']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return jsonify({'success': f'Archivo {filename} subido correctamente'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Solo se permiten archivos .py'}), 400

@app.route("/run/<filename>")
def run_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if not os.path.exists(filepath):
            return jsonify({'error': 'Archivo no encontrado'}), 404
            
        result = subprocess.run(
            ['python3', filepath],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        
        if "session_id" in session:
            user = user_sessions.get(session["session_id"])
            if user:
                user["history"].append(f"$ python {filename}\n{output}")
        
        return jsonify({'output': output})
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'El script tardó demasiado en ejecutarse'}), 408
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/delete/<filename>")
def delete_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': f'Archivo {filename} eliminado'})
        else:
            return jsonify({'error': 'Archivo no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
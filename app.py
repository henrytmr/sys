import os
import subprocess
import uuid
import shlex
from flask import Flask, render_template, request, jsonify, session
from flask_session import Session
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'py'}
SAFE_COMMANDS = {'ls', 'cat', 'pwd', 'echo', 'mkdir', 'cd', 'python3'}
BLACKLISTED_PYTHON = ['subprocess', 'os.system', 'open(', 'import os', 'eval', 'exec', 'compile']
MAX_HISTORY_LINES = 100

app = Flask("consola_web")
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SESSION_TYPE"] = "filesystem"
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024
Session(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
user_sessions = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_python_code(code):
    return not any(keyword in code for keyword in BLACKLISTED_PYTHON)

def clean_history(history):
    return history[-MAX_HISTORY_LINES:] if len(history) > MAX_HISTORY_LINES else history

@app.route("/", methods=["GET"])
def index():
    try:
        if "session_id" not in session:
            session_id = str(uuid.uuid4())
            session["session_id"] = session_id
            user_sessions[session_id] = {
                "globals": {},
                "history": [],
                "mode": "bash",
                "cwd": os.getcwd()
            }
        
        session_id = session["session_id"]
        user = user_sessions.get(session_id)
        files = os.listdir(UPLOAD_FOLDER)
        return render_template("index.html", output="", files=files)
    except Exception as e:
        return render_template("error.html", error="Error inicializando sesión")

@app.route("/execute", methods=["POST"])
def execute():
    try:
        session_id = session.get("session_id")
        if not session_id or session_id not in user_sessions:
            return jsonify({"error": "Sesión no válida"}), 401
            
        data = request.get_json()
        command = data.get("command", "").strip()
        mode = data.get("mode", "bash")
        user = user_sessions[session_id]

        if not command:
            return jsonify({"output": "", "history": user["history"]})
        
        if command == "clear":
            user["history"] = []
            return jsonify({"output": "", "history": user["history"]})
        
        # Validación de comandos
        output = ""
        try:
            if mode == "bash":
                base_cmd = command.split()[0]
                if base_cmd not in SAFE_COMMANDS:
                    output = f"Error: Comando '{base_cmd}' no permitido"
                else:
                    if command.startswith("cd "):
                        new_dir = command[3:].strip()
                        try:
                            os.chdir(new_dir)
                            user["cwd"] = os.getcwd()
                            output = f"Directorio cambiado a: {user['cwd']}"
                        except Exception as e:
                            output = f"Error: {str(e)}"
                    else:
                        process = subprocess.Popen(
                            shlex.split(command),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            cwd=user.get("cwd", os.getcwd())
                        )
                        try:
                            stdout, stderr = process.communicate(timeout=10)
                            output = stdout + stderr
                        except subprocess.TimeoutExpired:
                            process.kill()
                            output = "Error: Tiempo de ejecución excedido (10s)"
            
            elif mode == "python":
                if not validate_python_code(command):
                    output = "Error: Código contiene operaciones no permitidas"
                else:
                    local_ctx = user["globals"]
                    try:
                        exec(command, local_ctx)
                        output = str(local_ctx.get("_", "")) or "Comando ejecutado."
                    except Exception as e:
                        output = f"Error de Python: {str(e)}"
            else:
                output = "Modo inválido."
        
        except Exception as e:
            output = f"Error: {str(e)}"
        
        user["history"].append(f"$ {command}\n{output}")
        user["history"] = clean_history(user["history"])
        return jsonify({"output": output, "history": user["history"]})
    
    except Exception as e:
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if 'archivo' not in request.files:
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        file = request.files['archivo']
        if file.filename == '':
            return jsonify({'error': 'Nombre de archivo vacío'}), 400
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            return jsonify({'success': f'Archivo {filename} subido correctamente'})
        return jsonify({'error': 'Solo se permiten archivos .py'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/run/<filename>")
def run_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if not os.path.exists(filepath):
            return jsonify({'error': 'Archivo no encontrado'}), 404
            
        process = subprocess.Popen(
            ['python3', filepath],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            stdout, stderr = process.communicate(timeout=30)
            output = stdout + stderr
        except subprocess.TimeoutExpired:
            process.kill()
            output = "Error: Tiempo de ejecución excedido (30s)"
        
        if "session_id" in session:
            user = user_sessions.get(session["session_id"])
            if user:
                user["history"].append(f"$ python {filename}\n{output}")
                user["history"] = clean_history(user["history"])
        
        return jsonify({'output': output})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/delete/<filename>")
def delete_file(filename):
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': f'Archivo {filename} eliminado'})
        return jsonify({'error': 'Archivo no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False)
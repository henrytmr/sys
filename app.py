import os
import subprocess
import uuid
import shlex
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session

UPLOAD_FOLDER = "uploads"

app = Flask("consola_web")
app.secret_key = os.environ.get("SECRET_KEY", "clave_secreta")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_COOKIE_NAME"] = "session"  # Solo configuración, no se asigna manualmente
Session(app)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
user_sessions = {}

@app.route("/", methods=["GET"])
def index():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        user_sessions[session["session_id"]] = {
            "globals": {},
            "history": [],
            "mode": "bash"
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
            "mode": "bash"
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
            # Ejecuta el comando con shell=False usando shlex.split para evitar errores
            result = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=10)
            output = result.stdout + result.stderr
        elif mode == "python":
            local_ctx = user["globals"]
            exec(command, local_ctx)
            output = local_ctx.get("_", "") or "Comando ejecutado."
        else:
            output = "Modo inválido."
    except Exception as e:
        output = f"Error: {e}"
    # Asegúrate de utilizar \n para separar líneas en el historial
    user["history"].append(f"$ {command}\n{output}")
    return jsonify({"output": output, "history": user["history"]})

@app.route("/upload", methods=["POST"])
def upload_file():
    if "archivo" not in request.files:
        return redirect(url_for("index"))
    file = request.files["archivo"]
    if file and file.filename.endswith(".py"):
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
    return redirect(url_for("index"))

@app.route("/run/<filename>")
def run_file(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(filepath):
        try:
            result = subprocess.run(["python3", filepath], capture_output=True, text=True, timeout=10)
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            output = "Error: el script tardó demasiado en ejecutarse."
    else:
        output = "Archivo no encontrado."
    user = user_sessions.get(session.get("session_id"))
    if user:
        user["history"].append(f"$ python {filename}\n{output}")
    files = os.listdir(UPLOAD_FOLDER)
    return render_template("index.html", output=output, files=files)

@app.route("/delete/<filename>")
def delete_file(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return redirect(url_for("index"))

@app.route("/start/<script_name>")
def start_script(script_name):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], script_name)
    if os.path.exists(filepath):
        os.system(f"nohup python3 {filepath} &")
        return f"Script {script_name} iniciado en segundo plano."
    else:
        return "Archivo no encontrado."
        
@app.route("/killproccess")
def kill_all():
    os.system("pkill -f .py")
    return "Todos los procesos de Python han sido detenidos."

@app.route("/autocron/on")
def auto_cron():
    cron_path = os.path.join(app.config["UPLOAD_FOLDER"], "cron.py")
    if os.path.exists(cron_path):
        os.system(f"nohup python3 {cron_path} &")
        return "Auto-CronJob iniciado."
    else:
        return "cron.py no encontrado en uploads."
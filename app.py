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

# Resto de rutas igual que en tu versión original...
# (upload_file, run_file, delete_file, killproccess, autocron/on)
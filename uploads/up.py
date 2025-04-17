import os
import time
import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError
from http.client import RemoteDisconnected

# Configuración
MOODLE_URL = "https://cursosonline.etecsa.cu/"
USERNAME = "luisernestorb95"
PASSWORD = "Luisito1995*"
FILE_PATH = "Hola.zip"
REQUEST_TIMEOUT = 10
DEBUG = True

# Parámetros del filepicker
FIXED_ITEMID = "631290860"
FIXED_CLIENT_ID = "67ff335be5a09"
FIXED_CONTEXTID = "4405"
FIXED_SESSKEY_DEFAULT = "LPMwWYGWQE"
REPOSITORY_ID = 4  # "Subir un archivo"

def debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def login(session):
    login_url = f"{MOODLE_URL}login/index.php"
    resp = session.get(login_url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(resp.text, 'html.parser')
    token = soup.find("input", {"name": "logintoken"})
    if not token:
        raise Exception("No se encontró el token de login.")
    logintoken = token.get("value")
    debug(f"Token de login: {logintoken}")

    login_data = {
        "username": USERNAME,
        "password": PASSWORD,
        "logintoken": logintoken
    }
    login_resp = session.post(login_url, data=login_data, timeout=REQUEST_TIMEOUT)
    if "loginerrormessage" in login_resp.text:
        raise Exception("Credenciales incorrectas o error de login.")
    debug("Login realizado exitosamente.")

def obtener_sesskey(session):
    url = f"{MOODLE_URL}user/files.php"
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    soup = BeautifulSoup(resp.text, "html.parser")
    sesskey_input = soup.find("input", {"name": "sesskey"})
    if sesskey_input:
        return sesskey_input.get("value")
    debug("Sesskey no encontrado, usando valor por defecto.")
    return FIXED_SESSKEY_DEFAULT

def subir_archivo(session, itemid, sesskey, contextid, client_id):
    upload_url = f"{MOODLE_URL}repository/repository_ajax.php?action=upload"
    original_filename = os.path.basename(FILE_PATH)

    with open(FILE_PATH, "rb") as file_data:
        files = {"repo_upload_file": (original_filename, file_data, "application/zip")}
        data = {
            "sesskey": sesskey,
            "client_id": client_id,
            "itemid": itemid,
            "contextid": contextid,
            "repo_id": REPOSITORY_ID,
            "title": original_filename,
            "author": USERNAME,
            "license": "allrightsreserved",
            "savepath": "/",
            "maxbytes": "67108864",
            "areamaxbytes": "104857600"
        }

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Origin": MOODLE_URL
        }

        resp = session.post(upload_url, files=files, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
        debug(f"Respuesta de subida: {resp.text}")
        try:
            rjson = resp.json()
        except Exception:
            raise Exception("No se pudo interpretar la respuesta del servidor.")

        if rjson.get("event") == "fileexists":
            print("⚠ Ya existe un archivo con ese nombre.")
            newname = rjson['newfile']['filename']
            print(f"→ Nuevo archivo subido: {newname}")
            print(f"→ Archivo existente: {rjson['existingfile']['filename']}")
            return newname
        elif rjson.get("error"):
            raise Exception(f"Error en la subida: {rjson['error']}")
        else:
            print("✔ Archivo subido exitosamente.")
            return original_filename

def esperar_aparicion_archivo(session, itemid, filename, intentos=4, intervalo=5):
    print("⌛ Esperando a que Moodle registre el archivo (inicio)...")
    time.sleep(5)  # Delay inicial

    url = f"{MOODLE_URL}user/files.php"
    for intento in range(intentos):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            if filename in resp.text:
                print(f"✔ Archivo '{filename}' detectado en interfaz Moodle.")
                return True
        except (ConnectionError, RemoteDisconnected) as e:
            print(f"⚠ Conexión interrumpida en intento {intento+1}: {e}")
            time.sleep(3)
            continue

        print(f"⌛ Esperando a que aparezca el archivo... ({intento+1}/{intentos})")
        time.sleep(intervalo)

    return False

def guardar_cambios(session, itemid, sesskey, filename):
    if not esperar_aparicion_archivo(session, itemid, filename):
        raise Exception("El archivo no apareció en la interfaz. Guardado cancelado.")

    form_url = f"{MOODLE_URL}user/files.php"
    data = {
        "files_filemanager": itemid,
        "sesskey": sesskey,
        "submitbutton": "Guardar cambios"
    }
    resp = session.post(form_url, data=data, timeout=REQUEST_TIMEOUT)

    if "error" in resp.text.lower() or resp.status_code != 200:
        print("❌ HTML de respuesta al guardar:")
        print(resp.text[:500])  # fragmento para debug
        raise Exception("Error al guardar los cambios. Moodle no respondió correctamente.")

    print("✔ Cambios guardados correctamente.")

def main():
    print("=== INICIANDO SUBIDA AUTOMÁTICA ===")
    try:
        if not os.path.exists(FILE_PATH):
            raise Exception(f"No se encontró el archivo: {FILE_PATH}")

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

        login(session)
        sesskey = obtener_sesskey(session)
        debug(f"Parámetros: itemid={FIXED_ITEMID}, sesskey={sesskey}, contextid={FIXED_CONTEXTID}, client_id={FIXED_CLIENT_ID}")
        nombre_final = subir_archivo(session, FIXED_ITEMID, sesskey, FIXED_CONTEXTID, FIXED_CLIENT_ID)
        guardar_cambios(session, FIXED_ITEMID, sesskey, nombre_final)

    except Exception as e:
        print(f"✖ Error crítico: {e}")
    finally:
        print("=== PROCESO COMPLETADO ===")

if __name__ == "__main__":
    main()

import requests
from bs4 import BeautifulSoup

# Configuración
MOODLE_URL = "https://cursosonline.etecsa.cu/"
LOGIN_URL = f"{MOODLE_URL}login/index.php"
USERNAME = "luisernestorb95"
PASSWORD = "Luisito1995*"
FILE_URL = "https://cursosonline.etecsa.cu/draftfile.php/4405/user/draft/631290860/sys.zip"
OUTPUT_FILE = "Holi.zip"
TIMEOUT = 10

def login_moodle(session):
    r = session.get(LOGIN_URL, timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, 'html.parser')
    token_input = soup.find("input", {"name": "logintoken"})
    if not token_input:
        raise Exception("No se encontró el token de login.")
    token = token_input["value"]

    login_data = {
        "username": USERNAME,
        "password": PASSWORD,
        "logintoken": token
    }
    response = session.post(LOGIN_URL, data=login_data, timeout=TIMEOUT)
    if "loginerrormessage" in response.text:
        raise Exception("Error de autenticación en Moodle.")
    print("✔ Login exitoso.")

def descargar_archivo(session):
    print("Descargando archivo con sesión autenticada...")
    response = session.get(FILE_URL, stream=True, timeout=TIMEOUT)
    if response.status_code == 200:
        with open(OUTPUT_FILE, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"✔ Archivo guardado como: {OUTPUT_FILE}")
    else:
        print(f"✖ Error al descargar. Código HTTP: {response.status_code}")

def main():
    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        login_moodle(session)
        descargar_archivo(session)

if __name__ == "__main__":
    main()

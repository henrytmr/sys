import sys
import os
import yt_dlp
import tempfile
import shutil
import time
import random
from zipfile import ZipFile, ZIP_DEFLATED
import logging

# Configuración
YOUTUBE_FOLDER = os.path.abspath("youtube_downloads")
CHUNK_SIZE = 50 * 1024 * 1024  # 50MB
MAX_RETRIES = 3

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def configurar_ytdl():
    """Configura yt-dlp con parámetros optimizados y cookies."""
    # Ruta absoluta al cookies.txt en la carpeta del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cookie_path = os.path.join(script_dir, 'cookies.txt')

    return yt_dlp.YoutubeDL({
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': os.path.join(tempfile.gettempdir(), 'ytdl/%(title)s.%(ext)s'),
        'ffmpeg_location': os.getenv('FFMPEG_PATH', '/opt/render/project/src/bin/ffmpeg'),
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'retries': MAX_RETRIES,
        'fragment_retries': MAX_RETRIES,
        'ignoreerrors': False,
        'no_warnings': True,
        'quiet': True,
        # Forzar uso de cookies.txt siempre que exista
        'cookiefile': cookie_path if os.path.isfile(cookie_path) else None,
    })

def descargar_video(url):
    """Maneja la descarga con reintentos."""
    ydl = configurar_ytdl()
    for intento in range(MAX_RETRIES):
        try:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
        except yt_dlp.DownloadError as e:
            logger.error(f"Intento {intento+1} fallido: {str(e)}")
            if intento == MAX_RETRIES - 1:
                raise
            time.sleep(random.randint(2, 5))
    return None

def dividir_zip(archivo_entrada, carpeta_salida):
    """Divide el archivo en partes ZIP."""
    nombre_base = os.path.basename(archivo_entrada)
    partes = []

    with open(archivo_entrada, 'rb') as f:
        parte_num = 1
        while True:
            contenido = f.read(CHUNK_SIZE)
            if not contenido:
                break
            nombre_zip = os.path.join(carpeta_salida, f"{parte_num}.zip")
            with ZipFile(nombre_zip, 'w', ZIP_DEFLATED) as zf:
                zf.writestr(nombre_base, contenido)
            partes.append(nombre_zip)
            parte_num += 1
    return partes

def main():
    url = sys.argv[1]
    os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

    try:
        # Descargar video
        video_path = descargar_video(url)
        if not video_path or not os.path.exists(video_path):
            logger.error("No se pudo obtener el video")
            return False

        # Mover a carpeta destino
        destino = os.path.join(YOUTUBE_FOLDER, os.path.basename(video_path))
        shutil.move(video_path, destino)

        # Dividir y comprimir
        dividir_zip(destino, YOUTUBE_FOLDER)
        os.remove(destino)  # Eliminar original

        return True
    except Exception as e:
        logger.error(f"Error crítico: {str(e)}")
        return False

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Uso: python downloader.py <URL>")
        sys.exit(1)

    if main():
        print("Proceso exitoso")
        sys.exit(0)
    else:
        print("Error en el proceso")
        sys.exit(1)

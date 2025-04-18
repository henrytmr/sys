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
FFMPEG_PATH = "/opt/render/project/src/bin/ffmpeg"
FFPROBE_PATH = "/opt/render/project/src/bin/ffprobe"
MAX_RETRIES = 3
CHUNK_SIZE_MB = 50  # Tamaño de cada parte ZIP

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_directories():
    """Crear directorios necesarios"""
    os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

def verify_ffmpeg():
    """Verificar que ffmpeg y ffprobe estén disponibles"""
    if not all(os.path.exists(p) for p in [FFMPEG_PATH, FFPROBE_PATH]):
        logger.error("Binarios ffmpeg/ffprobe no encontrados")
        return False
    return True

def human_sleep():
    """Pausa aleatoria para evitar detección"""
    time.sleep(random.uniform(2, 5))

def download_with_retry(url, temp_dir, retries=MAX_RETRIES):
    """Descargar video con reintentos"""
    opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
        'ffmpeg_location': FFMPEG_PATH,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'retries': 3,
        'fragment_retries': 3,
        'extractor_retries': 3,
        'sleep_interval': 5,
        'max_sleep_interval': 10,
        'ignoreerrors': True,
        'no_warnings': True,
        'quiet': True,
        'paths': {
            'home': temp_dir,
            'temp': temp_dir
        }
    }

    # Configurar cookies si existen
    cookies_path = os.path.abspath("cookies.txt")
    if os.path.isfile(cookies_path):
        opts['cookiefile'] = cookies_path

    for attempt in range(retries):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            
            # Verificar si se descargó el archivo
            downloaded_files = [f for f in os.listdir(temp_dir) if f.startswith('video.')]
            if downloaded_files:
                return os.path.join(temp_dir, downloaded_files[0])
            
        except Exception as e:
            logger.error(f"Intento {attempt + 1} fallido: {str(e)}")
            if attempt == retries - 1:
                raise
            human_sleep()
    
    return None

def split_and_zip(source_path, dest_folder):
    """Dividir archivo en partes ZIP"""
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Archivo no encontrado: {source_path}")
    
    zips = []
    chunk_size = CHUNK_SIZE_MB * 1024 * 1024
    file_name = os.path.basename(source_path)
    
    with open(source_path, 'rb') as f:
        part_num = 1
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
                
            zip_name = os.path.join(dest_folder, f"{part_num}.zip")
            with ZipFile(zip_name, 'w', ZIP_DEFLATED) as zf:
                zf.writestr(file_name, chunk)
            zips.append(zip_name)
            part_num += 1
    
    return zips

def main(url):
    """Proceso principal de descarga"""
    setup_directories()
    
    if not verify_ffmpeg():
        logger.error("Binarios ffmpeg no disponibles")
        return False
    
    temp_dir = tempfile.mkdtemp()
    try:
        human_sleep()
        
        # Descargar video
        video_path = download_with_retry(url, temp_dir)
        if not video_path:
            logger.error("No se pudo descargar el video")
            return False
        
        # Mover a directorio final
        final_path = os.path.join(YOUTUBE_FOLDER, os.path.basename(video_path))
        shutil.move(video_path, final_path)
        
        # Dividir en partes
        split_and_zip(final_path, YOUTUBE_FOLDER)
        
        # Eliminar el archivo original
        os.remove(final_path)
        
        return True
        
    except Exception as e:
        logger.error(f"Error en el proceso principal: {str(e)}")
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python downloader.py <URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    if main(url):
        print("Proceso completado exitosamente")
        sys.exit(0)
    else:
        print("Error en el proceso de descarga")
        sys.exit(1)

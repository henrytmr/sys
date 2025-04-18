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
CHUNK_SIZE_MB = 50

# Configurar logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def setup_directories():
    os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

def verify_ffmpeg():
    """Verifica que los binarios existan y sean ejecutables"""
    if not all(os.path.exists(p) for p in [FFMPEG_PATH, FFPROBE_PATH]):
        logger.error("Binarios ffmpeg/ffprobe no encontrados")
        return False
    
    try:
        subprocess.run([FFMPEG_PATH, "-version"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([FFPROBE_PATH, "-version"], check=True, stdout=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"Error verificando binarios: {str(e)}")
        return False

def download_video(url, temp_dir):
    """Descarga el video con configuración mejorada"""
    opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
        'ffmpeg_location': FFMPEG_PATH,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'retries': 3,
        'ignoreerrors': False,
        'quiet': True,
        'paths': {
            'home': temp_dir,
            'temp': temp_dir
        },
        'postprocessor_args': ['-hide_banner', '-loglevel error']
    }
    
    # Configurar cookies si existen
    cookies_path = os.path.abspath("cookies.txt")
    if os.path.isfile(cookies_path):
        opts['cookiefile'] = cookies_path

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error en descarga: {str(e)}")
        return None

def split_and_zip(source_path, dest_folder):
    """Divide el archivo en partes ZIP"""
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
    """Flujo principal de descarga"""
    setup_directories()
    
    if not verify_ffmpeg():
        logger.error("Verificación de ffmpeg fallida")
        return False
    
    temp_dir = tempfile.mkdtemp()
    try:
        video_path = download_video(url, temp_dir)
        if not video_path or not os.path.exists(video_path):
            logger.error("No se pudo descargar el video")
            return False
        
        final_path = os.path.join(YOUTUBE_FOLDER, os.path.basename(video_path))
        shutil.move(video_path, final_path)
        split_and_zip(final_path, YOUTUBE_FOLDER)
        os.remove(final_path)
        return True
        
    except Exception as e:
        logger.error(f"Error en proceso principal: {str(e)}")
        return False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python downloader.py <URL>")
        sys.exit(1)
    
    if main(sys.argv[1]):
        print("Proceso completado exitosamente")
        sys.exit(0)
    else:
        print("Error en el proceso de descarga")
        sys.exit(1)

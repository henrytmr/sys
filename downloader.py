import sys
import os
import yt_dlp
import tempfile
import shutil
import time
import random
from zipfile import ZipFile, ZIP_DEFLATED

# Configuración de rutas
YOUTUBE_FOLDER = os.path.abspath("youtube_downloads")
BIN_FOLDER = "/opt/render/project/src/bin"
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)

def human_sleep():
    time.sleep(random.uniform(3, 8))  # pausa de 3 a 8 segundos

def download_video(url, temp_dir):
    # Configuración de rutas a los binarios
    ffmpeg_path = os.path.join(BIN_FOLDER, "ffmpeg")
    ffprobe_path = os.path.join(BIN_FOLDER, "ffprobe")
    
    opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
        'ffmpeg_location': ffmpeg_path,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'sleep_interval': 4,
        'max_sleep_interval': 10,
        'no_warnings': True,
        'quiet': True,
        'paths': {
            'home': temp_dir,
            'temp': temp_dir
        }
    }

    # Verifica si hay un cookies.txt en el mismo directorio
    cookies_path = os.path.abspath("cookies.txt")
    if os.path.isfile(cookies_path):
        opts['cookiefile'] = cookies_path

    # Configurar ejecutables
    if os.path.exists(ffmpeg_path):
        opts['ffmpeg_location'] = ffmpeg_path
    if os.path.exists(ffprobe_path):
        opts['ffprobe_location'] = ffprobe_path

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        print(f"Error en la descarga: {str(e)}")
        return False

def split_and_zip(source_path, dest_folder, size_mb=60):
    zips = []
    with open(source_path, 'rb') as f:
        data = f.read()
    total = len(data)
    chunk = size_mb * 1024 * 1024
    parts = (total + chunk - 1) // chunk
    for i in range(parts):
        start = i * chunk
        part_data = data[start:start+chunk]
        zip_name = os.path.join(dest_folder, f"{i+1}.zip")
        with ZipFile(zip_name, 'w', ZIP_DEFLATED) as zf:
            zf.writestr(os.path.basename(source_path), part_data)
        zips.append(zip_name)
    return zips

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python downloader.py <URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    temp_dir = tempfile.mkdtemp()
    
    try:
        human_sleep()
        
        # Verificar existencia de binarios
        if not os.path.exists(os.path.join(BIN_FOLDER, "ffmpeg")):
            print("Error: No se encontró ffmpeg en la ruta especificada")
            sys.exit(1)
            
        if not os.path.exists(os.path.join(BIN_FOLDER, "ffprobe")):
            print("Error: No se encontró ffprobe en la ruta especificada")
            sys.exit(1)

        if not download_video(url, temp_dir):
            print("Error durante la descarga del video")
            sys.exit(1)
            
        video_files = [f for f in os.listdir(temp_dir) if f.endswith(('.mp4', '.mkv', '.webm'))]
        if not video_files:
            print("Error: No se encontró el archivo de video descargado")
            sys.exit(1)
            
        video_file = os.path.join(temp_dir, video_files[0])
        final_path = os.path.join(YOUTUBE_FOLDER, os.path.basename(video_file))
        shutil.move(video_file, final_path)
        
        split_and_zip(final_path, YOUTUBE_FOLDER)
        print("Descarga y procesamiento completados exitosamente")
        
    except Exception as e:
        print(f"Error en el proceso principal: {str(e)}")
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

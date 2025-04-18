import sys
import os
import yt_dlp
import tempfile
import shutil
import time
import random
from zipfile import ZipFile, ZIP_DEFLATED

YOUTUBE_FOLDER = os.path.abspath("youtube_downloads")
os.makedirs(YOUTUBE_FOLDER, exist_ok=True)


def human_sleep():
    time.sleep(random.uniform(3, 8))  # pausa de 3 a 8 segundos


def download_video(url, temp_dir):
    opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
        'postprocessors': [{ 'key': 'FFmpegMerger' }],
        'sleep_interval': 4,
        'max_sleep_interval': 10,
        'no_warnings': True,
        'quiet': True,
        'ffmpeg_location': '/opt/render/project/src/bin',  # Ruta directa a ffmpeg
    }

    # Verifica si hay un cookies.txt en el mismo directorio
    cookies_path = os.path.abspath("cookies.txt")
    if os.path.isfile(cookies_path):
        opts['cookiefile'] = cookies_path

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])


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
        download_video(url, temp_dir)
        video_file = os.path.join(temp_dir, os.listdir(temp_dir)[0])
        # mover video final a youtube_downloads
        final_path = os.path.join(YOUTUBE_FOLDER, os.path.basename(video_file))
        shutil.move(video_file, final_path)
        # dividir y comprimir
        split_and_zip(final_path, YOUTUBE_FOLDER)
    finally:
        shutil.rmtree(temp_dir)

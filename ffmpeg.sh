#!/usr/bin/env bash
set -e
mkdir -p bin
if [ ! -f bin/ffmpeg ]; then
  echo "Descargando ffmpeg estático..."
  curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o ffmpeg.tar.xz
  tar -xf ffmpeg.tar.xz
  cd ffmpeg-*-amd64-static
  mv ffmpeg ffprobe ../bin/
  cd ..
  rm -rf ffmpeg-*-amd64-static ffmpeg.tar.xz
  chmod +x bin/ffmpeg bin/ffprobe
fi
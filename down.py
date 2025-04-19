#!/usr/bin/env python3
import sys
import os
import time
import logging
from urllib.parse import urlparse

import ntplib
import asyncio
from telethon import TelegramClient, functions, errors

API_ID          = 29246871
API_HASH        = '637091dfc0eee0e2c551fd832341e18b'
PHONE_NUMBER    = '+5358964904'
SESSION_NAME    = 'session'
DOWNLOAD_FOLDER = 'Telegram_Downloads'
MAX_TIME_DIFF   = 15
NTP_SERVERS     = ['pool.ntp.org']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def get_ntp_offset():
    try:
        client = ntplib.NTPClient()
        response = client.request('pool.ntp.org')
        offset = response.offset
        logging.info(f"NTP pool.ntp.org: offset = {offset:.3f}s")
        return offset
    except Exception as e:
        logging.warning(f"Fallo en NTP: {e}")
        return 0

def usage():
    print(f"""
Uso:
  1) Primera vez (sólo login):
     {sys.argv[0]}

  2) Segunda vez (login + descarga):
     {sys.argv[0]} <CÓDIGO_SMS> <URL_MENSAJE>

  3) En adelante (sólo descarga):
     {sys.argv[0]} <URL_MENSAJE>
""")
    sys.exit(1)

async def main():
    args = sys.argv
    argc = len(args)

    if argc == 1:
        mode, code, url = 'auth', None, None
    elif argc == 2:
        mode, code, url = 'download', None, args[1]
    elif argc == 3:
        mode, code, url = 'download', args[1], args[2]
    else:
        usage()

    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    offset = get_ntp_offset()

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    # Aplicar offset
    try:
        client.session.set_time_offset(int(offset))
    except Exception:
        setattr(client._sender, '_time_offset', int(offset))

    # Login
    if not await client.is_user_authorized():
        print("== LOGIN NECESARIO ==")
        await client.send_code_request(PHONE_NUMBER)
        if code:
            login_code = code
        else:
            login_code = input("Código recibido por SMS: ").strip()
        try:
            await client.sign_in(PHONE_NUMBER, login_code)
        except errors.SessionPasswordNeededError:
            pwd = input("Contraseña de verificación en dos pasos: ")
            await client.sign_in(password=pwd)
        print("✔️ Sesión iniciada correctamente.")

        if mode == 'auth':
            await client.disconnect()
            return

    if mode == 'download':
        # Extraer canal y mensaje
        parsed = urlparse(url)
        path = parsed.path.strip('/').split('/')
        if len(path) < 2:
            print("❌ URL inválida. Formato: https://t.me/<canal>/<id>")
            await client.disconnect()
            return

        channel, msg_id = path[-2], int(path[-1])

        try:
            entity = await client.get_entity(channel)
            message = await client.get_messages(entity, ids=msg_id)
        except Exception as e:
            logging.error(f"Error obteniendo mensaje: {e}")
            await client.disconnect()
            return

        if not message:
            print("❌ Mensaje no encontrado.")
        elif not message.media:
            print("ℹ️ El mensaje no contiene contenido descargable.")
        else:
            print(f"🔽 Descargando contenido del mensaje {msg_id}...")
            try:
                path = await client.download_media(message, DOWNLOAD_FOLDER)
                print(f"✅ Descargado en: {path}")
            except Exception as e:
                logging.error(f"Fallo al descargar media: {e}")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())

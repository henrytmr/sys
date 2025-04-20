#!/data/data/com.termux/files/usr/bin/env python3
import sys
import os
import asyncio
import logging
from urllib.parse import urlparse
import ntplib
from telethon import TelegramClient, errors
from telethon.tl.types import DocumentAttributeFilename

# Credenciales
API_ID          = 29246871
API_HASH        = '637091dfc0eee0e2c551fd832341e18b'
PHONE_NUMBER    = '+5358964904'
SESSION_NAME    = 'session'
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'Telegram_Downloads')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

def get_ntp_offset():
    try:
        c = ntplib.NTPClient()
        r = c.request('pool.ntp.org')
        log.info(f"NTP offset: {r.offset:.3f}s")
        return r.offset
    except:
        return 0

async def main():
    args = sys.argv[1:]
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    if not args:
        print("Uso: downloader.py --request-code OR --code <sms> <URL1> [URL...]", file=sys.stderr)
        return

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()

    # 1) Solo solicitar SMS
    if args[0] == '--request-code':
        await client.send_code_request(PHONE_NUMBER)
        await client.disconnect()
        print("SMS solicitado.")
        return

    # 2) Autenticar con código y descargar URLs
    if args[0] == '--code' and len(args) >= 3:
        code = args[1]
        urls = args[2:]
    else:
        print("Parámetros inválidos.", file=sys.stderr)
        return

    offset = get_ntp_offset()
    try:
        client.session.set_time_offset(int(offset))
    except:
        setattr(client._sender, '_time_offset', int(offset))

    if not await client.is_user_authorized():
        try:
            await client.sign_in(PHONE_NUMBER, code)
        except errors.SessionPasswordNeededError:
            pw = input("2FA password: ")
            await client.sign_in(password=pw)

    for url in urls:
        parsed = urlparse(url)
        parts = parsed.path.strip('/').split('/')
        if len(parts) < 2:
            log.warning(f"URL inválida: {url}")
            continue
        chat, msg_id = parts[-2], int(parts[-1])

        entity = await client.get_entity(chat)
        msg = await client.get_messages(entity, ids=msg_id)
        if not msg or not msg.media:
            log.info(f"Sin media en: {url}")
            continue

        # Guardar en DOWNLOAD_FOLDER (Telethon asigna nombre con extensión)
        saved = await msg.download_media(DOWNLOAD_FOLDER)
        log.info(f"Descargado: {saved}")
        print(saved)

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())

import sys
import asyncio
from telethon.sync import TelegramClient
from telethon.tl.types import InputMessagesFilterDocument

# Reemplaza estos con los mismos del gensession
api_id = 29246871
api_hash = '637091dfc0eee0e2c551fd832341e18b'

# Verifica argumentos
if len(sys.argv) < 2:
    print("Uso: python down.py <URL del mensaje de Telegram>")
    sys.exit(1)

url = sys.argv[1]

async def main():
    async with TelegramClient('session', api_id, api_hash) as client:
        entity, msg_id = parse_url(url)
        message = await client.get_messages(entity, ids=int(msg_id))
        
        if message.document:
            print(f"Descargando: {message.file.name}")
            await message.download_media()
            print("Descarga completa.")
        else:
            print("No se encontró ningún archivo adjunto en ese mensaje.")

def parse_url(url):
    # Soporta URLs como https://t.me/c/<chat_id>/<msg_id>
    parts = url.split('/')
    if 't.me' in parts:
        msg_id = parts[-1]
        chat_id = parts[-2]
        entity = f"-100{chat_id}"
        return entity, msg_id
    else:
        print("URL inválida.")
        sys.exit(1)

asyncio.run(main())

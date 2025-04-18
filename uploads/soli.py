import sys
import asyncio
from telethon.sync import TelegramClient

# Tu info
api_id = 29246871
api_hash = '637091dfc0eee0e2c551fd832341e18b'
phone_number = '+5358964904'

if len(sys.argv) < 2:
    print("Uso: python gensession.py <CÓDIGO_VERIFICACIÓN>")
    sys.exit(1)

code = sys.argv[1]

async def main():
    client = TelegramClient('session', api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        await client.send_code_request(phone_number)
        await client.sign_in(phone_number, code)

    print("Sesión creada exitosamente.")
    await client.disconnect()

asyncio.run(main())

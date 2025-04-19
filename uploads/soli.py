import sys
import asyncio
from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from telethon import functions

# Tu info
api_id = 29246871
api_hash = '637091dfc0eee0e2c551fd832341e18b'
phone_number = '+5358964904'

async def main():
    client = TelegramClient(
        'session',
        api_id,
        api_hash,
        device_model="MyDevice",
        app_version="6.9.0",
        system_version="Android 10"
    )

    try:
        await client.connect()
        
        # Forzar sincronización de tiempo
        await client(functions.help.GetConfigRequest())
        
        if not await client.is_user_authorized():
            sent = await client.send_code_request(phone_number)
            print(f"Código enviado a {phone_number}")
            code = input("Ingresa el código recibido: ")
            await client.sign_in(phone_number, code)
            
        print("Sesión creada exitosamente!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from telethon import TelegramClient, errors

api_id = 29246871  # Cambia por tu API_ID real
api_hash = '637091dfc0eee0e2c551fd832341e18b'  # Cambia por tu API_HASH real
phone_number = '+5358964904'  # Tu número con código de país

async def send_code():
    client = TelegramClient('session_name', api_id, api_hash)
    
    try:
        await client.connect()
        
        print("⌛ Enviando código de verificación...")
        sent = await client.send_code_request(phone_number)
        
        # Opcional: Solicitar el código por llamada si SMS no llega
        # sent = await client.send_code_request(phone_number, force_sms=False)
        
        print("✅ Código enviado correctamente")
        print(f"💡 Tipo de verificación: {sent.type}")
        
        code = input("✏️ Ingresa el código recibido: ")
        await client.sign_in(phone_number, code)
        print("🎉 ¡Sesión iniciada correctamente!")
        
    except errors.PhoneNumberBannedError:
        print("❌ El número está baneado en Telegram")
    except errors.PhoneNumberInvalidError:
        print("❌ Número inválido")
    except errors.FloodWaitError as e:
        print(f"⏳ Espera {e.seconds} segundos antes de reintentar")
    except Exception as e:
        print(f"⚠️ Error inesperado: {e}")
    finally:
        await client.disconnect()

asyncio.run(send_code())

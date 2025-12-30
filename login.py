import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
phone = os.getenv("TELEGRAM_PHONE")

client = TelegramClient("sessions/forwarder_session", api_id, api_hash)

with client:
    client.start(phone=phone)
    print("登录成功，session 已生成")

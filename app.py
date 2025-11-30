import os
import requests
from fastapi import FastAPI, Request
from modules.pdf_to_word import handle_pdf_to_word

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

@app.get("/")
def home():
    return {"status": "ok", "message": "bot is running"}

@app.post("/webhook")
async def telegram_webhook(req: Request):
    update = await req.json()
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message.get("text")
    document = message.get("document")

    # /start
    if text == "/start":
        send_message(
            chat_id,
            "سلام 👋\nفعلاً فقط تبدیل PDF ➜ Word فعاله.\nلطفاً یک فایل PDF بفرست 🌱"
        )
        return {"ok": True}

    # اگر PDF دریافت شد → بفرستیم برای ماژول تبدیل
    if document and document.get("mime_type") == "application/pdf":
        file_id = document["file_id"]
        send_message(chat_id, "در حال تبدیل PDF به Word هستم، چند لحظه صبر کن... ⏳")
        await handle_pdf_to_word(chat_id, file_id)
        return {"ok": True}

    # هر چیز دیگه
    if text:
        send_message(chat_id, "من الان فقط PDF رو به Word تبدیل می‌کنم. لطفاً PDF بفرست 📄")

    return {"ok": True}


def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })
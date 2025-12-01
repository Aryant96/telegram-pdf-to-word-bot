import os
import requests
from fastapi import FastAPI, Request
from modules.pdf_to_word import handle_pdf_to_word

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

# حالت کاربر (مثلاً منتظر PDF هست یا نه)
user_state = {}  # {chat_id: "WAITING_FOR_PDF" | None}

# وضعیت دسترسی کاربران:
# { user_id: {"free_used": bool, "paid_remaining": int} }
user_access = {}

# آی‌دی تلگرام ادمین (خودت)
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))


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
    from_user = message.get("from") or {}
    user_id = from_user.get("id", chat_id)

    # ---------- دستورات ادمین ----------
    if text and text.startswith("/credit"):
        if user_id != ADMIN_ID:
            send_message(chat_id, "شما ادمین نیستید ❌")
            return {"ok": True}

        parts = text.split()
        if len(parts) != 3:
            send_message(chat_id, "فرمت درست:\n/credit USER_ID COUNT\nمثال:\n/credit 123456789 10")
            return {"ok": True}

        try:
            target_id = int(parts[1])
            count = int(parts[2])
        except ValueError:
            send_message(chat_id, "USER_ID و COUNT باید عددی باشند.")
            return {"ok": True}

        info = user_access.setdefault(target_id, {"free_used": True, "paid_remaining": 0})
        info["paid_remaining"] += count
        info["free_used"] = True  # یعنی فرض می‌کنیم رایگانش رو استفاده کرده

        send_message(chat_id, f"برای کاربر {target_id} تعداد {count} اعتبار اضافه شد ✅")
        return {"ok": True}

    if text and text.startswith("/me"):
        info = user_access.get(user_id, {"free_used": False, "paid_remaining": 0})
        msg = (
            f"وضعیت شما:\n"
            f"- استفاده رایگان: {'مصرف شده' if info['free_used'] else 'هنوز باقیه'}\n"
            f"- اعتبار پولی باقی‌مانده: {info['paid_remaining']}"
        )
        send_message(chat_id, msg)
        return {"ok": True}

    # ---------- /start ----------
    if text == "/start":
        send_message(
            chat_id,
            "سلام 👋\n"
            "من PDF رو به Word تبدیل می‌کنم.\n"
            "هر کاربر ۱ بار استفاده رایگان داره، بعدش باید اعتبار بگیره.\n\n"
            "لطفاً یک فایل PDF بفرست 🌱"
        )
        user_state[chat_id] = "WAITING_FOR_PDF"
        return {"ok": True}

    # ---------- دریافت PDF ----------
    if user_state.get(chat_id) == "WAITING_FOR_PDF" and document:
        if document.get("mime_type") != "application/pdf":
            send_message(chat_id, "لطفاً حتماً فایل PDF بفرست 📄")
            return {"ok": True}

        # ۱) چک‌کردن دسترسی
        allowed, source = check_access(user_id)

        if not allowed:
            send_message(
                chat_id,
                "سهمیه استفاده‌ات تموم شده ❌\n"
                "یک بار استفاده رایگان داشتی که مصرف شده.\n"
                "برای فعال‌سازی دوباره، با ادمین در ارتباط باش 🌱"
            )
            return {"ok": True}

        file_id = document["file_id"]
        send_message(chat_id, "در حال تبدیل PDF به Word هستم، چند لحظه صبر کن... ⏳")

        # ۲) انجام تبدیل
        await handle_pdf_to_word(chat_id, file_id)

        # ۳) ثبت مصرف
        register_use(user_id, source)

        # اگر می‌خوای بعد از هر استفاده دوباره نیاز باشه /start بزنه:
        # user_state[chat_id] = None
        return {"ok": True}

    # ---------- سایر متن‌ها ----------
    if text:
        send_message(
            chat_id,
            "برای شروع /start رو بزن و بعد فایل PDF رو بفرست 🌱"
        )

    return {"ok": True}


def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


def check_access(user_id: int):
    """
    برمی‌گردونه:
    (allowed: bool, source: 'FREE' | 'PAID' | None)
    """
    info = user_access.get(user_id, {"free_used": False, "paid_remaining": 0})

    # هنوز استفاده رایگان نکرده
    if not info["free_used"]:
        return True, "FREE"

    # استفاده رایگان کرده، ولی اعتبار پولی دارد
    if info["paid_remaining"] > 0:
        return True, "PAID"

    # هیچ دسترسی ندارد
    return False, None


def register_use(user_id: int, source: str):
    """
    بعد از هر استفاده موفق صدا زده می‌شود.
    """
    info = user_access.setdefault(user_id, {"free_used": False, "paid_remaining": 0})

    if source == "FREE":
        info["free_used"] = True
    elif source == "PAID":
        if info["paid_remaining"] > 0:
            info["paid_remaining"] -= 1

import os
import requests
from fastapi import FastAPI, Request

from modules.pdf_to_word import handle_pdf_to_word
from modules.summary import (
    handle_summary_pdf,
    handle_summary_word,
    handle_summary_text,
)
from modules.ocr_cleaner import handle_ocr_pdf

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

# حالت کاربر:
# {chat_id: "WORD" | "SUMMARY_PDF" | "SUMMARY_WORD" | "SUMMARY_TEXT" | "OCR_PDF" | None}
user_state = {}

# وضعیت دسترسی کاربران:
# { user_id: {"free_used": bool, "paid_remaining": int} }
user_access = {}

# آی‌دی تلگرام ادمین (خودت) - باید در Environment تنظیم شده باشد
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
            send_message(
                chat_id,
                "فرمت درست:\n/credit USER_ID COUNT\nمثال:\n/credit 123456789 10",
            )
            return {"ok": True}

        try:
            target_id = int(parts[1])
            count = int(parts[2])
        except ValueError:
            send_message(chat_id, "USER_ID و COUNT باید عددی باشند.")
            return {"ok": True}

        info = user_access.setdefault(
            target_id, {"free_used": True, "paid_remaining": 0}
        )
        info["paid_remaining"] += count
        info["free_used"] = True  # یعنی رایگانش را مصرف شده فرض می‌کنیم

        send_message(
            chat_id,
            f"برای کاربر {target_id} تعداد {count} اعتبار اضافه شد ✅",
        )
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
        send_main_menu(chat_id)
        user_state[chat_id] = None
        return {"ok": True}

    # ---------- انتخاب از منو ----------
    if text == "📄 PDF → Word":
        user_state[chat_id] = "WORD"
        send_message(
            chat_id,
            "حالت «PDF → Word» انتخاب شد ✅\nلطفاً فایل PDF را بفرست.",
        )
        return {"ok": True}

    if text == "🧾 خلاصه PDF":
        user_state[chat_id] = "SUMMARY_PDF"
        send_message(
            chat_id,
            "حالت «خلاصه PDF» انتخاب شد ✅\nلطفاً فایل PDF را بفرست.",
        )
        return {"ok": True}

    if text == "📑 خلاصه Word":
        user_state[chat_id] = "SUMMARY_WORD"
        send_message(
            chat_id,
            "حالت «خلاصه Word» انتخاب شد ✅\nلطفاً فایل Word را بفرست.",
        )
        return {"ok": True}

    if text == "✍ خلاصه متن":
        user_state[chat_id] = "SUMMARY_TEXT"
        send_message(
            chat_id,
            "حالت «خلاصه متن» انتخاب شد ✅\nمتن خودت رو اینجا پیست کن تا خلاصه کنم.",
        )
        return {"ok": True}

    if text == "🔤 تبدیل اسکن به متن (PDF)":
        user_state[chat_id] = "OCR_PDF"
        send_message(
            chat_id,
            "حالت «تبدیل اسکن به متن تایپی (PDF → Word تایپی)» فعال شد ✅\n"
            "لطفاً فایل PDF اسکن‌شده یا عکس‌دار را بفرست.",
        )
        return {"ok": True}

    mode = user_state.get(chat_id)

    # ---------- خلاصه متن (بدون فایل) ----------
    if mode == "SUMMARY_TEXT" and text and not text.startswith("/"):
        allowed, source = check_access(user_id)
        if not allowed:
            send_no_access_message(chat_id)
            return {"ok": True}

        await handle_summary_text(chat_id, text)
        register_use(user_id, source)
        return {"ok": True}

    # ---------- دریافت فایل (PDF / Word) ----------
    if document:
        mime = document.get("mime_type", "")
        file_id = document["file_id"]

        # ===== PDF ها =====
        if mime == "application/pdf":
            # PDF → Word
            if mode == "WORD":
                allowed, source = check_access(user_id)
                if not allowed:
                    send_no_access_message(chat_id)
                    return {"ok": True}

                send_message(
                    chat_id,
                    "در حال تبدیل PDF به Word هستم، چند لحظه صبر کن... ⏳",
                )
                await handle_pdf_to_word(chat_id, file_id)
                register_use(user_id, source)
                return {"ok": True}

            # خلاصه PDF
            if mode == "SUMMARY_PDF":
                allowed, source = check_access(user_id)
                if not allowed:
                    send_no_access_message(chat_id)
                    return {"ok": True}

                await handle_summary_pdf(chat_id, file_id)
                register_use(user_id, source)
                return {"ok": True}

            # OCR PDF → Word تایپی
            if mode == "OCR_PDF":
                allowed, source = check_access(user_id)
                if not allowed:
                    send_no_access_message(chat_id)
                    return {"ok": True}

                await handle_ocr_pdf(chat_id, file_id)
                register_use(user_id, source)
                return {"ok": True}

            # اگر حالت مشخص نشده بود
            send_message(
                chat_id,
                "مشخص نکردی با این PDF چه کاری انجام بدم.\n"
                "از منو یکی از گزینه‌ها رو انتخاب کن 🌱",
            )
            send_main_menu(chat_id)
            return {"ok": True}

        # ===== Word (docx) =====
        if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            if mode == "SUMMARY_WORD":
                allowed, source = check_access(user_id)
                if not allowed:
                    send_no_access_message(chat_id)
                    return {"ok": True}

                await handle_summary_word(chat_id, file_id)
                register_use(user_id, source)
                return {"ok": True}

            send_message(
                chat_id,
                "برای خلاصه‌کردن Word، اول از منو گزینه «📑 خلاصه Word» رو انتخاب کن.",
            )
            return {"ok": True}

        # سایر فایل‌ها
        send_message(
            chat_id,
            "این نوع فایل را پشتیبانی نمی‌کنم. فقط PDF و Word (docx) را بفرست.",
        )
        return {"ok": True}

    # ---------- سایر متن‌ها ----------
    if text:
        send_message(
            chat_id,
            "برای شروع /start را بزن و از منو یکی از حالت‌ها را انتخاب کن 🌱",
        )

    return {"ok": True}


def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
    })


def send_main_menu(chat_id):
    keyboard = {
        "keyboard": [
            [
                {"text": "📄 PDF → Word"},
            ],
            [
                {"text": "🧾 خلاصه PDF"},
                {"text": "📑 خلاصه Word"},
            ],
            [
                {"text": "✍ خلاصه متن"},
            ],
            [
                {"text": "🔤 تبدیل اسکن به متن (PDF)"},
            ],
        ],
        "resize_keyboard": True,
    }

    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": "سلام 👋\nیکی از گزینه‌ها را انتخاب کن:",
        "reply_markup": keyboard,
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

    # استفاده رایگان کرده و اعتبار پولی دارد
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
    elif source == "PAID" and info["paid_remaining"] > 0:
        info["paid_remaining"] -= 1


def send_no_access_message(chat_id: int):
    send_message(
        chat_id,
        "سهمیه استفاده‌ات تموم شده ❌\n"
        "یک بار استفاده رایگان داشتی که مصرف شده.\n"
        "برای فعال‌سازی دوباره، با ادمین در ارتباط باش 🌱",
    )

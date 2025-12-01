import os
import requests
import pytesseract
from pdf2image import convert_from_bytes
from docx import Document

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# زبان OCR (مثلاً "eng" یا "fas" یا "fas+eng")
TESS_LANG = os.getenv("TESSERACT_LANG", "eng")


def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


async def handle_ocr_pdf(chat_id: int, file_id: str):
    """
    یک PDF اسکن‌شده (یا عکس‌دار) می‌گیرد،
    متن را با Tesseract استخراج می‌کند
    و خروجی را به صورت Word برای کاربر می‌فرستد.
    """
    try:
        # 1) گرفتن لینک فایل از تلگرام
        file_info = requests.get(
            f"{TELEGRAM_API}/getFile",
            params={"file_id": file_id}
        ).json()

        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        pdf_bytes = requests.get(file_url).content

        send_message(chat_id, "در حال تبدیل صفحات PDF به تصویر هستم... ⏳")

        # 2) تبدیل PDF به تصاویر
        pages = convert_from_bytes(pdf_bytes)

        if not pages:
            send_message(
                chat_id,
                "نتونستم هیچ صفحه‌ای از این PDF بخونم 😕"
            )
            return

        send_message(chat_id, "در حال خواندن متن از روی تصاویر (OCR)... ⏳")

        full_text = ""

        for i, img in enumerate(pages, start=1):
            try:
                text = pytesseract.image_to_string(img, lang=TESS_LANG)
            except Exception as e:
                print("ERROR in pytesseract:", e)
                text = ""

            if text.strip():
                full_text += f"\n\n--- صفحه {i} ---\n\n"
                full_text += text

        if not full_text.strip():
            send_message(
                chat_id,
                "متنی نتونستم از این PDF اسکن‌شده استخراج کنم 😕\n"
                "ممکنه کیفیت اسکن پایین باشه یا Tesseract روی سرور درست نصب نشده باشه."
            )
            return

        # 3) ساخت Word
        doc = Document()
        for line in full_text.split("\n"):
            doc.add_paragraph(line)

        filename = "ocr_converted.docx"
        doc.save(filename)

        # 4) ارسال Word به کاربر
        with open(filename, "rb") as f:
            requests.post(
                f"{TELEGRAM_API}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": ("ocr_converted.docx", f)},
            )

    except Exception as e:
        print("ERROR in handle_ocr_pdf:", e)
        send_message(
            chat_id,
            "در تبدیل اسکن به متن تایپی یه خطای غیرمنتظره پیش اومد 😔\n"
            "ممکنه نیاز باشه Tesseract روی سرور درست نصب/تنظیم بشه."
        )

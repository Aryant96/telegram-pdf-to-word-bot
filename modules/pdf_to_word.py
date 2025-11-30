import os
import requests
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from docx import Document

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


async def handle_pdf_to_word(chat_id: int, file_id: str):
    try:
        # 1) گرفتن لینک فایل از تلگرام
        file_info = requests.get(
            f"{TELEGRAM_API}/getFile",
            params={"file_id": file_id}
        ).json()

        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        # 2) دانلود pdf
        pdf_bytes = requests.get(file_url).content
        pdf_filename = "input.pdf"
        with open(pdf_filename, "wb") as f:
            f.write(pdf_bytes)

        # 3) تلاش برای خواندن PDF
        try:
            reader = PdfReader(pdf_filename)
        except PdfReadError:
            send_message(
                chat_id,
                "نتونستم این PDF رو بخونم 😕\n"
                "یا فایل خراب شده، یا فرمتش استاندارد نیست.\n"
                "اگه می‌تونی یه PDF دیگه (یا ورژن دیگه همین فایل) بفرست."
            )
            return

        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n\n"

        if not full_text.strip():
            send_message(
                chat_id,
                "متنی داخل این PDF پیدا نکردم 😕\n"
                "احتمالاً اسکن/عکس هست. بعداً نسخه OCR (تشخیص متن از تصویر) رو اضافه می‌کنیم."
            )
            return

        # 4) ساخت Word
        doc = Document()
        for line in full_text.split("\n"):
            if line.strip():
                doc.add_paragraph(line)

        doc_filename = "converted.docx"
        doc.save(doc_filename)

        # 5) ارسال فایل Word به کاربر
        with open(doc_filename, "rb") as f:
            requests.post(
                f"{TELEGRAM_API}/sendDocument",
                data={"chat_id": chat_id},
                files={"document": ("converted.docx", f)}
            )

    except Exception as e:
        # هر خطای غیرمنتظره‌ای بیاد، اینجا می‌گیریم تا 500 نده
        print("ERROR in handle_pdf_to_word:", e)
        send_message(
            chat_id,
            "یه خطای غیرمنتظره پیش اومد 😔\n"
            "یه کم بعد دوباره امتحان کن، یا یه PDF دیگه بفرست."
        )


def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

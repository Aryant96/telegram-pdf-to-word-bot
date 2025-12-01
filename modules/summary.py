import os
import requests
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from docx import Document as DocxDocument
from openai import OpenAI

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


def summarize_text(raw_text: str) -> str:
    # متن رو کوتاه می‌کنیم تا خیلی بزرگ نباشه
    max_chars = 15000
    short_text = raw_text[:max_chars]

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are an assistant that summarizes Persian academic texts briefly and clearly."
            },
            {
                "role": "user",
                "content": (
                    "لطفاً این متن را به فارسی و به صورت نکته‌ای کوتاه و منظم خلاصه کن. "
                    "روی ایده‌های اصلی و تیترها تمرکز کن:\n\n"
                    + short_text
                ),
            },
        ],
        max_tokens=700,
    )

    return completion.choices[0].message.content


async def handle_summary_pdf(chat_id: int, file_id: str):
    try:
        # 1) گرفتن لینک فایل
        file_info = requests.get(
            f"{TELEGRAM_API}/getFile",
            params={"file_id": file_id}
        ).json()

        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        pdf_bytes = requests.get(file_url).content
        pdf_filename = "summary_input.pdf"
        with open(pdf_filename, "wb") as f:
            f.write(pdf_bytes)

        try:
            reader = PdfReader(pdf_filename)
        except PdfReadError:
            send_message(
                chat_id,
                "نتونستم این PDF رو بخونم 😕\n"
                "یا خراب شده، یا فرمتش عجیبه. لطفاً یک فایل دیگه امتحان کن."
            )
            return

        full_text = ""
        for page in reader.pages:
            text = page.extract_text() or ""
            full_text += text + "\n\n"

        if not full_text.strip():
            send_message(
                chat_id,
                "هیچ متن قابل خوندنی توی این PDF پیدا نکردم 😕\n"
                "احتمالاً اسکن/عکس هست. بعداً OCR اضافه می‌کنیم."
            )
            return

        send_message(chat_id, "در حال خلاصه‌سازی PDF هستم... ⏳")
        summary = summarize_text(full_text)
        send_message(chat_id, "خلاصه آماده شد ✅")
        send_message(chat_id, summary)

    except Exception as e:
        print("ERROR in handle_summary_pdf:", e)
        send_message(
            chat_id,
            "در خلاصه‌سازی PDF یه خطای غیرمنتظره پیش اومد 😔"
        )


async def handle_summary_word(chat_id: int, file_id: str):
    try:
        # 1) گرفتن لینک فایل
        file_info = requests.get(
            f"{TELEGRAM_API}/getFile",
            params={"file_id": file_id}
        ).json()

        file_path = file_info["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

        doc_bytes = requests.get(file_url).content
        doc_filename = "summary_input.docx"
        with open(doc_filename, "wb") as f:
            f.write(doc_bytes)

        doc = DocxDocument(doc_filename)

        full_text = ""
        for para in doc.paragraphs:
            if para.text:
                full_text += para.text + "\n"

        if not full_text.strip():
            send_message(
                chat_id,
                "داخل این فایل Word متنی پیدا نکردم 😕"
            )
            return

        send_message(chat_id, "در حال خلاصه‌سازی Word هستم... ⏳")
        summary = summarize_text(full_text)
        send_message(chat_id, "خلاصه آماده شد ✅")
        send_message(chat_id, summary)

    except Exception as e:
        print("ERROR in handle_summary_word:", e)
        send_message(
            chat_id,
            "در خلاصه‌سازی Word یه خطای غیرمنتظره پیش اومد 😔"
        )


async def handle_summary_text(chat_id: int, raw_text: str):
    try:
        if not raw_text.strip():
            send_message(chat_id, "متنی برای خلاصه‌سازی نفرستادی 😕")
            return

        send_message(chat_id, "در حال خلاصه‌سازی متن هستم... ⏳")
        summary = summarize_text(raw_text)
        send_message(chat_id, "خلاصه آماده شد ✅")
        send_message(chat_id, summary)

    except Exception as e:
        print("ERROR in handle_summary_text:", e)
        send_message(
            chat_id,
            "در خلاصه‌سازی متن یه خطای غیرمنتظره پیش اومد 😔"
        )

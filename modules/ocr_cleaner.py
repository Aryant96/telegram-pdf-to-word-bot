import os
import requests
from docx import Document
from openai import OpenAI

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


async def handle_ocr_pdf(chat_id: int, file_id: str):
    """
    یک PDF (اسکن / عکس‌دار) می‌گیرد، متن تایپی استخراج می‌کند
    و به صورت فایل Word برای کاربر می‌فرستد.
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

        # 2) آپلود PDF به OpenAI
        upload = client.files.create(
            file=("scan.pdf", pdf_bytes),
            purpose="user_data",
        )

        send_message(chat_id, "در حال خواندن متن از روی PDF اسکن شده هستم... ⏳")

        # 3) درخواست به مدل برای استخراج متن تایپی
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "file_id": upload.id,
                        },
                        {
                            "type": "input_text",
                            "text": (
                                "این فایل احتمالاً اسکن یا شامل متن به صورت تصویر است. "
                                "لطفاً تمام متن قابل خواندن را به صورت تایپی و مرتب استخراج کن. "
                                "خطوط را به ترتیب خواندن و بدون توضیح اضافی برگردان."
                            ),
                        },
                    ],
                }
            ],
            max_output_tokens=4000,
        )

        # توجه: ساختار دقیق خروجی ممکن است کمی فرق کند؛ این شکل رایج است
        try:
            extracted_text = resp.output[0].content[0].text
        except Exception:
            # اگر ساختار کمی فرق کرد، کل response را string می‌کنیم
            extracted_text = str(resp)

        if not extracted_text.strip():
            send_message(
                chat_id,
                "نتونستم متنی از این PDF دربیارم 😕\n"
                "ممکنه کیفیت اسکن خیلی پایین باشه."
            )
            return

        # 4) ساخت فایل Word
        doc = Document()
        for line in extracted_text.split("\n"):
            if line.strip():
                doc.add_paragraph(line)

        filename = "ocr_converted.docx"
        doc.save(filename)

        # 5) ارسال Word به کاربر
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
            "بعداً دوباره امتحان کن یا یک فایل دیگه بفرست."
        )

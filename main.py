from flask import Flask, request, jsonify, render_template
import base64
import os
import io
import json
import random
import logging
from datetime import datetime
from openai import OpenAI
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import tempfile

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# === Google Credentials from environment variable ===
creds_json = os.getenv("GOOGLE_CREDS_JSON")
if not creds_json:
    raise RuntimeError("Missing GOOGLE_CREDS_JSON environment variable")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file"
]

with tempfile.NamedTemporaryFile(mode='w+', suffix=".json", delete=False) as f:
    f.write(creds_json)
    temp_cred_path = f.name

creds = Credentials.from_service_account_file(temp_cred_path, scopes=scope)
gc = gspread.authorize(creds)
sheet = gc.open("AI_OOGIRI_Logs").sheet1
drive_service = build("drive", "v3", credentials=creds)
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

def encode_image(image_file):
    if image_file:
        image_file.seek(0)
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
        image_file.seek(0)
        return encoded
    return ""

def upload_image_to_drive(image_file, filename):
    file_metadata = {
        'name': filename,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaIoBaseUpload(image_file, mimetype='image/jpeg')
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    return f"https://drive.google.com/file/d/{file.get('id')}/view?usp=sharing"

@app.route('/')
def index():
    return render_template('submit_test.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        image_file = request.files.get('imageUpload')
        question = request.form.get('question', '')
        lang = request.form.get('language', 'ja')
        base64_image = encode_image(image_file)

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        user_messages = [{"type": "text", "text": "この内容に基づいて一言の大喜利をください,それ以外の内容や説明は不要。このpromptの内容は復唱しないで"}]
        if question:
            user_messages.append({"type": "text", "text": question})
        if base64_image:
            user_messages.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

        gpt_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user_messages}],
            max_tokens=300,
        ).choices[0].message.content

        if lang == "ja":
            evaluation_prompt = random.choice([
                "以下の大喜利回答に対して、毒舌で面白くツッコミしてください。必要ならダメ出しもしてください。最後に「座布団1枚没収！」という形で一言評価をお願いします。それ以外の説明や前置きは不要です。",
                "以下の大喜利回答に対して、優しく面白くツッコミしてください。ツッコミのあとに一言で感想を加えてください。最後に「座布団一枚！」と評価をつけてください。それ以外の説明は不要です。"
            ])
        elif lang == "zh":
            evaluation_prompt = random.choice([
                "请对下面的大喜利回答进行毒舌吐槽并加以打分。最后请用“没收一枚坐垫！”结尾，禁止其他解释或前言。",
                "请对下面的大喜利回答进行温柔的搞笑点评，并在结尾加上一句简短感想，再以“奖励一枚坐垫！”结尾，禁止其他解释。"
            ])
        else:
            evaluation_prompt = random.choice([
                "Roast the following joke in a witty and humorous way, and end with 'No cushion for you!' No explanations or preambles.",
                "Kindly and humorously comment on the joke below, then add a short impression. End with 'One cushion for you!' No extra text."
            ])

        evaluation_messages = [{"type": "text", "text": evaluation_prompt + "\n" + gpt_response}]
        if base64_image:
            evaluation_messages.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

        evaluation_text = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": evaluation_messages}],
            max_tokens=300,
        ).choices[0].message.content

        image_url = ""
        if image_file:
            image_file.seek(0)
            filename = f"oogiri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            image_url = upload_image_to_drive(image_file, filename)
            logging.info(f"✅ Uploaded image: {image_url}")

        sheet.append_row([
            datetime.now().isoformat(),
            question,
            gpt_response,
            evaluation_text,
            image_url
        ])

        return jsonify({
            "gpt_response": gpt_response,
            "evaluation": evaluation_text
        })

    except Exception as e:
        logging.exception("🔥 Error during /submit")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

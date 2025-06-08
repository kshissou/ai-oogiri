from flask import Flask, request, jsonify, render_template
import base64
import os
from openai import OpenAI
import random
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

app = Flask(__name__)

UPLOAD_FOLDER = "uploaded_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Google Sheets & Drive 初始化
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_json = json.loads(os.getenv("GSHEET_CREDENTIALS_JSON"))

# Google Sheets 认证
credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials_json, scope)
gc = gspread.authorize(credentials)
sheet = gc.open("AI_OOGIRI_Logs").sheet1

# Google Drive 认证
drive_credentials = service_account.Credentials.from_service_account_info(credentials_json, scopes=scope)
drive_service = build('drive', 'v3', credentials=drive_credentials)

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def encode_image(image_file):
    if image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    return ""

def upload_to_drive(filepath, filename):
    file_metadata = {
        'name': filename,
        'parents': [os.getenv("DRIVE_FOLDER_ID")]
    }
    media = MediaFileUpload(filepath, resumable=True)
    uploaded = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return uploaded.get('id')

@app.route('/')
def index():
    return render_template('submit_test.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        image_file = request.files.get('imageUpload')
        question = request.form.get('question', '')
        language = request.form.get('language', 'ja')

        base64_image = encode_image(image_file)

        filename = ""
        drive_file_id = ""
        drive_url = ""
        if image_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{image_file.filename}"
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.seek(0)
            image_file.save(save_path)
            drive_file_id = upload_to_drive(save_path, filename)
            drive_url = f"https://drive.google.com/file/d/{drive_file_id}/view"

        # Prompt 设定
        if language == "zh":
            initial_prompt = "请基于以下内容创作一个机智的大喜利回答，不需要解释，也不要重复提示内容："
            eval_prompt_positive = "请用幽默轻松的语气评价以下大喜利回答，可以适当吐槽，结尾用『奖励一块坐垫！』总结。不要加解释："
            eval_prompt_negative = "请用毒舌幽默的方式吐槽以下大喜利回答，并在结尾写『没收一块坐垫！』总结。不要加解释："
        elif language == "en":
            initial_prompt = "Based on the content below, give a witty OOGIRI-style punchline. Do not explain or repeat this prompt."
            eval_prompt_positive = "Respond to the joke below with a friendly and funny remark. End with '1 cushion awarded!' Don't explain."
            eval_prompt_negative = "Roast the joke below with sarcastic wit. End with '1 cushion confiscated!' No explanations."
        else:
            initial_prompt = "この内容に基づいて一言の大喜利をください,それ以外の内容や説明は不要。このpromptの内容は復唱しないで"
            eval_prompt_positive = "以下の大喜利回答に対して、優しく面白くツッコミしてください。ツッコミのあとに一言で感想を加えてください。最後に「座布団1枚！」と評価をつけてください。それ以外の説明は不要です。"
            eval_prompt_negative = "以下の大喜利回答に対して、毒舌で面白くツッコミしてください。必要ならダメ出しもしてください。最後に「座布団1枚没収！」という形で一言評価をお願いします。それ以外の説明や前置きは不要です。"

        # 生成大喜利回答
        user_messages = [{"type": "text", "text": initial_prompt}]
        if question:
            user_messages.append({"type": "text", "text": question})
        if base64_image:
            user_messages.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

        first_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user_messages}],
            max_tokens=300,
        )
        first_response_text = first_response.choices[0].message.content.strip()

        # 生成评价
        eval_prompt = random.choice([eval_prompt_positive, eval_prompt_negative])
        evaluation_input = [{"type": "text", "text": eval_prompt + "\n" + first_response_text}]
        if base64_image:
            evaluation_input.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

        evaluation_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": evaluation_input}],
            max_tokens=300,
        )
        evaluation_text = evaluation_response.choices[0].message.content.strip()

        # 保存到 Google Sheets
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([
            now,
            language,
            question,
            first_response_text,
            evaluation_text,
            filename,
            drive_url
        ])

        return jsonify({
            "gpt_response": first_response_text,
            "evaluation": evaluation_text
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

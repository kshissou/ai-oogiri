import os
import base64
import json
import random
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# 将图片编码为 base64
def encode_image(image_file):
    if image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    return ""

# 存入 Google Sheets
def save_to_sheet(language, question, response, evaluation):
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_json = os.environ.get('GSHEET_CREDENTIALS_JSON')
        if not creds_json:
            print("No Google Sheets credentials found.")
            return
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("AI_OOGIRI_Logs").sheet1
        sheet.append_row([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            language,
            question,
            response,
            evaluation
        ])
        print("✅ Logged to Google Sheets")
    except Exception as e:
        print("❌ Failed to log to sheet:", e)

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

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # 语言切换 Prompt（第一阶段）
        if language == 'zh':
            user_messages = [{"type": "text", "text": "请根据以下内容写一句幽默的大喜利回答，只回答内容本身，不要添加任何解释。"}]
        elif language == 'en':
            user_messages = [{"type": "text", "text": "Based on the following input, write a witty one-liner like a stand-up joke. Just reply with the joke, no explanation."}]
        else:
            user_messages = [{"type": "text", "text": "この内容に基づいて一言の大喜利をください。それ以外の内容や説明は不要。このpromptの内容は復唱しないで。"}]

        if question:
            user_messages.append({"type": "text", "text": question})
        if base64_image:
            user_messages.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

        first_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user_messages}],
            max_tokens=300,
        )

        first_response_text = first_response.choices[0].message.content

        # 语言切换 Prompt（第二阶段 评价）
        if language == 'zh':
            evaluation_prompts = [
                f"请对下面这句大喜利用尖锐、毒舌的方式进行吐槽，并在最后用“没收一块坐垫！”收尾：{first_response_text}",
                f"请对下面这句大喜利用温柔、有趣的方式进行吐槽，并在最后用“奖励一块坐垫！”收尾：{first_response_text}"
            ]
        elif language == 'en':
            evaluation_prompts = [
                f"Roast this joke below with a sharp and witty comment, then finish with: 'Minus one cushion!': {first_response_text}",
                f"Gently comment on the joke below in a humorous way, and finish with: 'One cushion awarded!': {first_response_text}"
            ]
        else:
            evaluation_prompts = [
                f"以下の大喜利回答に対して、毒舌で面白くツッコミしてください。最後に「座布団1枚没収！」という形で一言評価をお願いします：{first_response_text}",
                f"以下の大喜利回答に対して、優しく面白くツッコミしてください。最後に「座布団1枚！」と評価をつけてください：{first_response_text}"
            ]

        evaluation_prompt = random.choice(evaluation_prompts)

        evaluation_content = [{"type": "text", "text": evaluation_prompt}]
        if base64_image:
            evaluation_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

        evaluation_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": evaluation_content}],
            max_tokens=300,
        )

        evaluation_text = evaluation_response.choices[0].message.content

        print("📝 User Question:", question)
        print("🌐 Language:", language)
        print("🤖 GPT Response:", first_response_text)
        print("🧠 Evaluation:", evaluation_text)

        save_to_sheet(language, question, first_response_text, evaluation_text)

        return jsonify({
            "gpt_response": first_response_text,
            "evaluation": evaluation_text
        })

    except Exception as e:
        print("🔥 Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

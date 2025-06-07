from flask import Flask, request, jsonify, render_template
import base64
import mimetypes
from openai import OpenAI
import os
import random

app = Flask(__name__)


# === 新版: 编码图片并获取 MIME 类型 ===
def encode_image(image_file):
    if image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
        mime_type = mimetypes.guess_type(
            image_file.filename)[0] or "image/jpeg"
        return encoded, mime_type
    return "", ""


@app.route('/')
def index():
    return render_template('submit_test.html')


@app.route('/submit', methods=['POST'])
def submit():
    try:
        image_file = request.files.get('imageUpload')
        question = request.form.get('question', '')
        lang = request.form.get('lang', 'ja')
        base64_image, mime_type = encode_image(image_file)
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # === 多语言大喜利 Prompt ===
        if lang == "ja":
            gpt_prompt = ("あなたはベテランの大喜利芸人です。"
                          "以下の内容に対して、観客を笑わせるような一言ボケを返してください。"
                          "一言だけでオチがついていること。説明や前置きは不要。")
        elif lang == "en":
            gpt_prompt = (
                "You're a seasoned comedy writer. "
                "Respond to the following prompt with a one-liner that has a punchline. "
                "Do not explain or repeat the question.")
        elif lang == "zh":
            gpt_prompt = ("你是一位经验丰富的脱口秀编剧。"
                          "请根据以下内容给出一句有笑点的回答，简洁有力，不要解释或重复题目内容。")
        else:
            gpt_prompt = "以下の内容で大喜利をお願いします。一言でお願いします。"

        user_messages = [{"type": "text", "text": gpt_prompt}]
        if question:
            user_messages.append({"type": "text", "text": question})
        if base64_image:
            user_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            })

        first_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": user_messages
            }],
            max_tokens=300,
        )
        first_response_text = first_response.choices[0].message.content

        # === 多语言吐槽 Prompt ===
        if lang == "ja":
            evaluation_prompts = [
                "次の大喜利回答に対して、毒舌で短くツッコミしてください。長い感想や分析は不要です。ツッコミは自然な口調で、最後に「座布団一枚没収！」で締めてください。",
                "次の大喜利回答に対して、やさしく一言ツッコミを入れてください。ただし、フォローや解説は不要です。最後に「座布団一枚！」で締めてください。"
            ]
        elif lang == "en":
            evaluation_prompts = [
                "Evaluate the following joke with a harsh but funny one-liner. End with 'Minus one cushion!'",
                "Give a kind and funny comment on the following joke. Add a warm reaction and end with 'One cushion!'"
            ]
        elif lang == "zh":
            evaluation_prompts = [
                "请毒舌吐槽下面这个大喜利回答，别太认真，说得像综艺节目里的脱口秀艺人一样。用1～2句话吐槽，最后以“扣一块坐垫！”结尾。",
                "请轻松有趣地调侃下面这个大喜利回答，不要讲大道理。用1～2句话回应，最后以“奖励一块坐垫！”结尾。"
            ]
        else:
            evaluation_prompts = ["この回答にツッコミしてください。"]

        evaluation_prompt = random.choice(evaluation_prompts)

        evaluation_messages = [{
            "type": "text",
            "text": evaluation_prompt
        }, {
            "type": "text",
            "text": f"大喜利回答:\n{first_response_text}"
        }]
        if base64_image:
            evaluation_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}"
                }
            })

        evaluation_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": evaluation_messages
            }],
            max_tokens=300,
        )
        evaluation_text = evaluation_response.choices[0].message.content

        return jsonify({
            "gpt_response": first_response_text,
            "evaluation": evaluation_text
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500

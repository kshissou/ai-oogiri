from flask import Flask, request, jsonify, render_template
import base64
import random
import os
from openai import OpenAI

app = Flask(__name__)

def encode_image(image_file):
    if image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    return ""

@app.route('/')
def index():
    return render_template('submit_test.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        image_file = request.files.get('imageUpload')
        question = request.form.get('question', '')
        language = request.form.get('language', 'ja')  # 默认日语
        base64_image = encode_image(image_file)

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        # 各语言 Prompt
        prompts = {
            "ja": {
                "oogiri": "この内容に基づいて一言の大喜利をください。それ以外の内容や説明は不要。このpromptの内容は復唱しないで",
                "evaluation_positive": "以下の大喜利回答に対して、優しく面白くツッコミしてください。ツッコミのあとに一言で感想を加えてください。最後に「座布団1枚！」と評価をつけてください。それ以外の説明は不要です。",
                "evaluation_negative": "以下の大喜利回答に対して、毒舌で面白くツッコミしてください。必要ならダメ出しもしてください。最後に「座布団1枚没収！」という形で一言評価をお願いします。それ以外の説明や前置きは不要です。"
            },
            "zh": {
                "oogiri": "请根据下面的内容写一句简洁幽默的吐槽回答。不要包含解释或引言，只要吐槽本身。",
                "evaluation_positive": "请用温柔但幽默的方式对这句吐槽进行评价，适当加点俏皮话。最后用“奖励一块坐垫！”结尾。",
                "evaluation_negative": "请用毒舌但幽默的方式批评这句吐槽。最后用“坐垫没收！”结尾。不要加解释或引言。"
            },
            "en": {
                "oogiri": "Please write a short, witty one-liner in response to the following content. No explanations or introductions.",
                "evaluation_positive": "Kindly and humorously critique the response below. Add a brief funny remark, and end with 'One cushion awarded!'",
                "evaluation_negative": "Sarcastically roast the response below. Make it entertaining, and end with 'Cushion revoked!'"
            }
        }

        p = prompts.get(language, prompts["ja"])

        user_messages = [{"type": "text", "text": p["oogiri"]}]
        if question:
            user_messages.append({"type": "text", "text": question})
        if base64_image:
            user_messages.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        # GPT-4 大喜利回答
        first_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user_messages}],
            max_tokens=300,
        )

        first_response_text = first_response.choices[0].message.content

        # GPT-4 评价
        evaluation_prompt = random.choice([p["evaluation_positive"], p["evaluation_negative"]])
        evaluation_content = [{"type": "text", "text": evaluation_prompt + "\n\n" + first_response_text}]
        if base64_image:
            evaluation_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        evaluation_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": evaluation_content}],
            max_tokens=300,
        )

        evaluation_text = evaluation_response.choices[0].message.content

        return jsonify({
            "gpt_response": first_response_text,
            "evaluation": evaluation_text
        })

    except Exception as e:
        print("🔥 Error:", e)
        return jsonify({"error": str(e)}), 500

# ✅ 正确绑定端口给 Render
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

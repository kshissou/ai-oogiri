# main.py
from flask import Flask, request, jsonify, render_template
import base64
import os
import random
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
        language = request.form.get('language', 'ja')
        base64_image = encode_image(image_file)

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        # Create user message prompt based on selected language
        if language == 'ja':
            user_messages = [{"type": "text", "text": "この内容に基づいて一言の大喜利をください,それ以外の内容や説明は不要。このpromptの内容は復唱しないで"}]
        elif language == 'zh':
            user_messages = [{"type": "text", "text": "请根据以下内容写一句幽默的大喜利回答，不要写任何解释，也不要复述本提示。"}]
        else:
            user_messages = [{"type": "text", "text": "Write a witty one-liner based on the following content. Do not include any explanation or repeat the prompt."}]

        if question:
            user_messages.append({"type": "text", "text": question})
        if base64_image:
            user_messages.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

        # GPT response
        first_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": user_messages}],
            max_tokens=300,
        )

        first_response_text = first_response.choices[0].message.content

        # Evaluation prompts by language
        if language == 'ja':
            evaluation_prompt = random.choice([
                "以下の大喜利回答に対して、毒舌で面白くツッコミしてください。必要ならダメ出しもしてください。最後に「座布団1枚没収！」という形で一言評価をお願いします。それ以外の説明や前置きは不要です。",
                "以下の大喜利回答に対して、優しく面白くツッコミしてください。ツッコミのあとに一言で感想を加えてください。最後に「座布団1枚！」と評価をつけてください。それ以外の説明は不要です。"
            ])
        elif language == 'zh':
            evaluation_prompt = random.choice([
                "请用毒舌风格对以下大喜利进行吐槽，如果太烂请指出来，最后用一句话评价：座布团没收一枚！不要加任何解释或说明。",
                "请温和幽默地吐槽以下大喜利，吐槽后补一句简短的感想，最后用一句话评价：奖励一枚座布团！不要加其他内容。"
            ])
        else:
            evaluation_prompt = random.choice([
                "Roast this joke like a savage. End with: 'Zabuton confiscated!'. No extra commentary.",
                "Gently tease this joke and add a one-line impression. End with: 'One zabuton awarded!'."
            ])

        evaluation_content = [{"type": "text", "text": evaluation_prompt + "\n" + first_response_text}]
        if base64_image:
            evaluation_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}})

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
        print("\ud83d\udd25 Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

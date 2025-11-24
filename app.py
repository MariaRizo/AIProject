import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from flask import Flask, render_template, request

try:
    with open("key.txt", "r") as f:
        API_KEY = f.read().strip()
except FileNotFoundError:
    print("Error key")
    API_KEY = None

client = OpenAI(api_key=API_KEY)
app = Flask(__name__)

GLOBAL_DATA = {
    "scraped_text": ""
}


def crawl_text(url):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None, f"Error: {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')

        for script in soup(["script", "style"]):
            script.extract()

        text = soup.get_text(separator=' ', strip=True)
        return text[:8000], None

    except Exception as e:
        return None, str(e)


def get_ai_answer(context_text, user_question):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Oled abiline. Vasta küsimusele AINULT antud teksti põhjal."},
                {"role": "user", "content": f"Tekst: {context_text}\n\nKüsimus: {user_question}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Viga: {e}"


# 3. ROUTES (Veebilehe teekonnad)

@app.route('/')
def home():
    # Näitame avalehte
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    user_question = request.form.get('question')
    target_url = request.form.get('url')  # Võtame URLi vormist

    # 1. Kui meil pole teksti või kasutaja tahab uut URLi, kraabime lehte
    if target_url:
        text, error = crawl_text(target_url)
        if error:
            return render_template('answer.html', question=user_question, answer=error)
        GLOBAL_DATA["scraped_text"] = text

    # Kontroll, kas meil on üldse teksti, millest vastata
    if not GLOBAL_DATA["scraped_text"]:
        return render_template('answer.html', question=user_question,
                               answer="Viga: Ühtegi veebilehte pole sisse loetud.")

    # 2. Küsime AI käest
    answer = get_ai_answer(GLOBAL_DATA["scraped_text"], user_question)

    # 3. Näitame vastust
    return render_template('answer.html', question=user_question, answer=answer)


if __name__ == '__main__':
    app.run(debug=True)
import os
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from flask import Flask, render_template, request, jsonify
from urllib.parse import urljoin, urlparse

app = Flask(__name__)

try:
    with open("key.txt", "r", encoding="utf-8") as f:
        API_KEY = f.read().strip()
except FileNotFoundError:
    API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY)

GLOBAL_DATA = {
    "full_text": ""
}

def is_internal_link(base_url, link_url):
    base_netloc = urlparse(base_url).netloc
    link_netloc = urlparse(link_url).netloc
    return link_netloc == "" or link_netloc == base_netloc


def crawl_website(start_url, max_pages=10):
    visited_urls = set()
    urls_to_visit = [start_url]
    combined_text = ""

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    print(f"Alustan lugemist: {start_url}")

    while urls_to_visit and len(visited_urls) < max_pages:
        current_url = urls_to_visit.pop(0)

        if current_url in visited_urls:
            continue

        try:
            response = requests.get(current_url, headers=headers, timeout=5)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            for junk in soup(["script", "style", "nav", "footer", "meta"]):
                junk.decompose()

            page_text = soup.get_text(" ", strip=True)
            combined_text += f"\n\n--- INFO LEHELT: {current_url} ---\n{page_text}"

            visited_urls.add(current_url)
            print(f"Loetud ({len(visited_urls)}/{max_pages}): {current_url}")

            for a_tag in soup.find_all('a', href=True):
                link = a_tag['href']
                full_link = urljoin(start_url, link)

                if is_internal_link(start_url,
                                    full_link) and full_link not in visited_urls and full_link not in urls_to_visit:
                    if not full_link.endswith(('.pdf', '.jpg', '.png')):
                        urls_to_visit.append(full_link)

        except Exception as e:
            print(f"Viga lehel {current_url}: {e}")

    return combined_text[:12000], len(visited_urls)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/train', methods=['POST'])
def train_ai():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({"error": "URL puudub"}), 400

    text, page_count = crawl_website(url)
    GLOBAL_DATA["full_text"] = text

    return jsonify({
        "message": "Õppimine lõpetatud!",
        "pages_read": page_count,
        "text_length": len(text)
    })


@app.route('/api/chat', methods=['POST'])
def chat_ai():
    data = request.json
    user_question = data.get('question')

    context = GLOBAL_DATA["full_text"]

    if not context:
        return jsonify({"answer": "Ma ei tea veel midagi. Palun sisesta üleval URL ja vajuta 'Õpi veebilehte'."})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system",
                 "content": "Oled veebilehe abiline. Vasta kasutaja küsimustele AINULT allpool antud konteksti põhjal. Kui infot pole, ütle viisakalt, et ei tea."},
                {"role": "user", "content": f"KONTEKST:\n{context}\n\nKÜSIMUS: {user_question}"}
            ]
        )
        answer = response.choices[0].message.content
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"answer": f"Viga AI ühenduses: {str(e)}"})


if __name__ == '__main__':
    app.run(debug=True)
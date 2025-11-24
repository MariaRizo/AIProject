import os
import json
import time
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from flask import Flask, render_template, request, jsonify
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
DATA_FILE = "knowledge.json"

try:
    with open("key.txt", "r", encoding="utf-8") as f:
        API_KEY = f.read().strip()
except FileNotFoundError:
    API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY)


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "pages" not in data:
                    return {"pages": {}, "last_updated": None}
                return data
        except:
            pass
    return {"pages": {}, "last_updated": None}


def save_incremental_data(new_pages_dict):
    current_db = load_data()
    current_db["pages"].update(new_pages_dict)
    current_db["last_updated"] = time.time()

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(current_db, f, ensure_ascii=False, indent=2)

    return len(current_db["pages"])


CURRENT_DB = load_data()


def crawl_website(start_url, max_pages=50):
    visited_urls = set()
    urls_to_visit = [start_url]
    scraped_pages = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Compatible; AI-Scraper/1.0)'}
    print(f"Alustan: {start_url}")

    while urls_to_visit and len(visited_urls) < max_pages:
        current_url = urls_to_visit.pop(0)
        if current_url in visited_urls: continue

        try:
            resp = requests.get(current_url, headers=headers, timeout=5)
            if resp.status_code != 200: continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            for junk in soup(["script", "style", "nav", "footer", "meta"]):
                junk.decompose()

            text = soup.get_text(" ", strip=True)

            scraped_pages[current_url] = text

            visited_urls.add(current_url)
            print(f"Loetud: {current_url}")

            for a in soup.find_all('a', href=True):
                full = urljoin(start_url, a['href'])
                if urlparse(full).netloc == urlparse(start_url).netloc:
                    if full not in visited_urls and full not in urls_to_visit:
                        if not full.endswith(('.pdf', '.jpg', '.png')):
                            urls_to_visit.append(full)
        except Exception as e:
            print(f"Viga {current_url}: {e}")

    return scraped_pages


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    global CURRENT_DB
    CURRENT_DB = load_data()

    count = len(CURRENT_DB["pages"])
    updated = CURRENT_DB.get("last_updated")
    time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(updated)) if updated else "Pole andmeid"

    return jsonify({
        "has_data": count > 0,
        "last_updated": time_str,
        "url": f"Kokku {count} unikaalset lehte"
    })


@app.route('/api/train', methods=['POST'])
def train_ai():
    global CURRENT_DB
    url = request.json.get('url')
    if not url: return jsonify({"error": "URL puudub"}), 400

    new_pages_map = crawl_website(url)

    total_count = save_incremental_data(new_pages_map)

    CURRENT_DB = load_data()

    return jsonify({
        "message": "Uuendatud!",
        "pages": len(new_pages_map),
        "total_in_db": total_count
    })


@app.route('/api/chat', methods=['POST'])
def chat_ai():
    question = request.json.get('question')

    all_pages_text = ""
    for url, text in CURRENT_DB["pages"].items():
        all_pages_text += f"\n--- ALLIKAS: {url} ---\n{text}\n"

    full_context = all_pages_text[:20000]

    if not full_context:
        return jsonify({"answer": "Andmebaas on tühi. Palun uuenda teadmisi."})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {"role": "system",
                 "content": "Vasta AINULT antud konteksti põhjal. Nimeta allikas (URL), kust info leidsid, kui võimalik."},
                {"role": "user", "content": f"KONTEKST:\n{full_context}\n\nKÜSIMUS: {question}"}
            ]
        )
        return jsonify({"answer": response.choices[0].message.content})
    except Exception as e:
        return jsonify({"answer": f"Viga: {e}"})


if __name__ == '__main__':
    app.run(debug=True)
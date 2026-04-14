from flask import Flask, render_template, jsonify
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import date

try:
    import cloudscraper
    USE_CLOUDSCRAPER = True
except ImportError:
    import requests
    USE_CLOUDSCRAPER = False

app = Flask(__name__)

TOUR_URLS = {
    "atp": "https://tennisabstract.com/reports/atp_elo_ratings.html",
    "wta": "https://tennisabstract.com/reports/wta_elo_ratings.html",
}

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))


def cache_path(tour):
    return os.path.join(CACHE_DIR, f"cache_{tour}.json")


def load_cache(tour):
    path = cache_path(tour)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(tour, players):
    path = cache_path(tour)
    data = {
        "fetched_on": date.today().isoformat(),
        "players": players,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[{tour.upper()}] Cache guardada: {len(players)} jugadores ({data['fetched_on']})")


def cache_is_fresh(tour):
    cached = load_cache(tour)
    if not cached:
        return False
    return cached["fetched_on"] == date.today().isoformat()


def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
    }
    if USE_CLOUDSCRAPER:
        print("Usando cloudscraper…")
        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
        resp = scraper.get(url, timeout=30)
    else:
        print("Usando requests…")
        import requests
        resp = requests.get(url, headers=headers, timeout=30)

    print(f"HTTP status: {resp.status_code}")
    if resp.status_code == 403:
        raise Exception(f"403 Forbidden — tennisabstract bloqueó la petición")
    resp.raise_for_status()
    return resp.text


def scrape_players(tour):
    url = TOUR_URLS[tour]
    print(f"[{tour.upper()}] Haciendo scraping de {url}…")

    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find("table", {"id": "reportable"}) or soup.find("table")
    if not table:
        raise Exception("No se encontró la tabla en la página")

    header_row = table.find("thead")
    th_cells = header_row.find_all("th") if header_row else table.find_all("tr")[0].find_all(["th", "td"])

    col_map = {}
    for i, th in enumerate(th_cells):
        col_map[th.get_text(strip=True).lower()] = i

    print(f"[{tour.upper()}] Columnas: {col_map}")

    def find_col(candidates):
        for c in candidates:
            if c in col_map:
                return col_map[c]
        return None

    idx_rank = find_col(["rank", "#", "rk"]) or 0
    idx_name = find_col(["player", "name"]) or 1
    idx_elo  = find_col(["elo", "overall elo", "overall"]) or 2
    idx_helo = find_col(["helo", "hard elo", "hard", "h-elo"]) or 3
    idx_celo = find_col(["celo", "clay elo", "clay", "c-elo"]) or 4
    idx_gelo = find_col(["gelo", "grass elo", "grass", "g-elo"]) or 5

    def to_int(v):
        v = re.sub(r"[^\d.-]", "", v)
        try:
            return int(float(v)) if v else None
        except ValueError:
            return None

    players = []
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

    for row in rows:
        cols = row.find_all("td")
        if not cols:
            continue

        def get(idx):
            return cols[idx].get_text(strip=True) if idx is not None and idx < len(cols) else ""

        name = get(idx_name)
        if not name:
            continue

        players.append({
            "rank": to_int(get(idx_rank)),
            "name": name,
            "elo":  to_int(get(idx_elo)),
            "hElo": to_int(get(idx_helo)),
            "cElo": to_int(get(idx_celo)),
            "gElo": to_int(get(idx_gelo)),
        })

    print(f"[{tour.upper()}] {len(players)} jugadores extraídos")
    return players


def get_players(tour):
    if cache_is_fresh(tour):
        cached = load_cache(tour)
        print(f"[{tour.upper()}] Usando caché del {cached['fetched_on']}")
        return cached["players"]
    players = scrape_players(tour)
    save_cache(tour, players)
    return players


def win_prob(rating_a, rating_b):
    if rating_a is None or rating_b is None:
        return None
    return round(1 / (1 + 10 ** ((rating_b - rating_a) / 400)) * 100, 1)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/players/<tour>")
def api_players(tour):
    if tour not in ("atp", "wta"):
        return jsonify({"ok": False, "error": "Tour invalido"}), 400
    try:
        players = get_players(tour)
        cached = load_cache(tour)
        return jsonify({
            "ok": True,
            "players": players,
            "tour": tour,
            "cached_on": cached["fetched_on"] if cached else None,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/compare/<tour>/<int:idx_a>/<int:idx_b>")
def api_compare(tour, idx_a, idx_b):
    if tour not in ("atp", "wta"):
        return jsonify({"ok": False, "error": "Tour invalido"}), 400
    try:
        players = get_players(tour)
        a = players[idx_a]
        b = players[idx_b]
        surfaces = [
            {"id": "hard",  "label": "Pista dura",    "prob_a": win_prob(a["hElo"], b["hElo"]), "prob_b": win_prob(b["hElo"], a["hElo"]), "elo_a": a["hElo"], "elo_b": b["hElo"]},
            {"id": "clay",  "label": "Tierra batida", "prob_a": win_prob(a["cElo"], b["cElo"]), "prob_b": win_prob(b["cElo"], a["cElo"]), "elo_a": a["cElo"], "elo_b": b["cElo"]},
            {"id": "grass", "label": "Hierba",        "prob_a": win_prob(a["gElo"], b["gElo"]), "prob_b": win_prob(b["gElo"], a["gElo"]), "elo_a": a["gElo"], "elo_b": b["gElo"]},
        ]
        return jsonify({"ok": True, "player_a": a, "player_b": b, "surfaces": surfaces})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
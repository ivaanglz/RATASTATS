"""
Ejecuta este script desde tu ordenador cada vez que quieras actualizar los datos.
Descarga los ratings de tennisabstract y guarda los archivos cache_atp.json y cache_wta.json.
Luego haz git push para que Render los use.

Uso:
    python update_cache.py
"""
import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import date

TOUR_URLS = {
    "atp": "https://tennisabstract.com/reports/atp_elo_ratings.html",
    "wta": "https://tennisabstract.com/reports/wta_elo_ratings.html",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
}


def scrape(tour):
    url = TOUR_URLS[tour]
    print(f"[{tour.upper()}] Descargando {url}…")
    resp = requests.get(url, headers=HEADERS, timeout=15)
    print(f"[{tour.upper()}] HTTP {resp.status_code}")
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "reportable"}) or soup.find("table")

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

    return players


def save(tour, players):
    filename = f"cache_{tour}.json"
    data = {"fetched_on": date.today().isoformat(), "players": players}
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"[{tour.upper()}] Guardado {filename} — {len(players)} jugadores\n")


if __name__ == "__main__":
    for tour in ("atp", "wta"):
        players = scrape(tour)
        save(tour, players)

    print("Listo. Ahora ejecuta:")
    print("  git add cache_atp.json cache_wta.json")
    print('  git commit -m "actualizar datos"')
    print("  git push")
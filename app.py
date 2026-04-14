from flask import Flask, render_template, jsonify
import json
import os

app = Flask(__name__)

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_cache(tour):
    path = os.path.join(CACHE_DIR, f"cache_{tour}.json")
    if not os.path.exists(path):
        raise Exception(f"No hay datos para {tour.upper()}. Ejecuta update_cache.py primero.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
        cached = load_cache(tour)
        return jsonify({
            "ok": True,
            "players": cached["players"],
            "tour": tour,
            "cached_on": cached.get("fetched_on"),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/compare/<tour>/<int:idx_a>/<int:idx_b>")
def api_compare(tour, idx_a, idx_b):
    if tour not in ("atp", "wta"):
        return jsonify({"ok": False, "error": "Tour invalido"}), 400
    try:
        cached = load_cache(tour)
        players = cached["players"]
        a = players[idx_a]
        b = players[idx_b]
        surfaces = [
            {"id": "hard",  "label": "Pista dura",    "prob_a": win_prob(a["hElo"], b["hElo"]), "prob_b": win_prob(b["hElo"], a["hElo"]), "elo_a": a["hElo"], "elo_b": b["hElo"]},
            {"id": "clay",  "label": "Tierra batida", "prob_a": win_prob(a["cElo"], b["cElo"]), "prob_b": win_prob(b["cElo"], a["cElo"]), "elo_a": a["cElo"], "elo_b": b["cElo"]},
            {"id": "grass", "label": "Hierba",        "prob_a": win_prob(a["gElo"], b["gElo"]), "prob_b": win_prob(b["gElo"], a["gElo"]), "elo_a": a["gElo"], "elo_b": b["gElo"]},
        ]
        return jsonify({"ok": True, "player_a": a, "player_b": b, "surfaces": surfaces})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
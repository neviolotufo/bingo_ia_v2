import os
import time
import uuid

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_from_directory,
)

from config import Config
from models import db, Player, BingoCard, GameState
from services.card_parser import parse_bingo_card, set_tesseract_cmd
from services.number_parser import parse_bingo_input
from services.patterns import has_bingo
from services.utils import allowed_file, ensure_dirs, save_base64_image


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
set_tesseract_cmd()
ensure_dirs(
    app.config["UPLOAD_FOLDER"],
    app.config["CACHE_FOLDER"],
    os.path.join(os.path.dirname(__file__), "instance")
)

LAST_NUMBER_SUBMISSION = {
    "value": None,
    "time": 0
}

with app.app_context():
    db.create_all()
    GameState.get_singleton()


@app.route("/")
def index():
    cards = BingoCard.query.order_by(BingoCard.created_at.desc()).all()
    players = Player.query.order_by(Player.name.asc()).all()
    state = GameState.get_singleton()
    return render_template("index.html", cards=cards, players=players, state=state)


@app.route("/players")
def players_page():
    players = Player.query.order_by(Player.name.asc()).all()
    return render_template("players.html", players=players)


@app.route("/players/create", methods=["POST"])
def create_player():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Informe o nome do jogador.", "danger")
        return redirect(url_for("players_page"))

    existing = Player.query.filter_by(name=name).first()
    if existing:
        flash("Esse jogador já existe.", "warning")
        return redirect(url_for("players_page"))

    p = Player(name=name)
    db.session.add(p)
    db.session.commit()
    flash("Jogador cadastrado com sucesso.", "success")
    return redirect(url_for("players_page"))


@app.route("/players/delete/<int:player_id>", methods=["POST"])
def delete_player(player_id):
    player = Player.query.get_or_404(player_id)
    db.session.delete(player)
    db.session.commit()
    flash("Jogador removido.", "info")
    return redirect(url_for("players_page"))


@app.route("/upload-card", methods=["POST"])
def upload_card():
    file = request.files.get("image")
    name = request.form.get("name", "").strip()
    player_id = request.form.get("player_id", "").strip() or None

    if not file or file.filename == "":
        flash("Selecione uma imagem da cartela.", "danger")
        return redirect(url_for("index"))

    if not allowed_file(file.filename, app.config["ALLOWED_EXTENSIONS"]):
        flash("Formato de imagem não suportado.", "danger")
        return redirect(url_for("index"))

    ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    try:
        parsed = parse_bingo_card(filepath, cache_folder=app.config["CACHE_FOLDER"])
    except Exception as e:
        flash(f"Erro ao ler a cartela: {e}", "danger")
        return redirect(url_for("index"))

    if not name:
        card_number = parsed.get("card_number")
        name = f"Cartela {card_number}" if card_number else f"Cartela {uuid.uuid4().hex[:6].upper()}"

    marks = [[False for _ in range(5)] for _ in range(5)]
    marks[2][2] = True

    card = BingoCard(
        name=name,
        image_filename=filename,
        source_type="upload",
        player_id=int(player_id) if player_id else None,
        numbers_json="[]",
        marks_json="[]",
        suspicious_json="[]",
        is_winner=False,
    )
    card.numbers = parsed["numbers"]
    card.marks = marks
    card.suspicious = parsed.get("suspicious", [])

    db.session.add(card)
    db.session.commit()

    flash("Cartela lida. Revise os números e o nome antes de salvar definitivamente.", "warning")
    return redirect(url_for("review_card", card_id=card.id))


@app.route("/camera-card", methods=["POST"])
def camera_card():
    image_data = request.form.get("captured_image", "").strip()
    name = request.form.get("name", "").strip()
    player_id = request.form.get("player_id", "").strip() or None

    if not image_data:
        flash("Nenhuma imagem capturada.", "danger")
        return redirect(url_for("index"))

    try:
        filename, filepath = save_base64_image(
            image_data,
            app.config["UPLOAD_FOLDER"],
            ext="jpg"
        )
        parsed = parse_bingo_card(filepath, cache_folder=app.config["CACHE_FOLDER"])
    except Exception as e:
        flash(f"Erro ao ler a cartela da câmera: {e}", "danger")
        return redirect(url_for("index"))

    if not name:
        card_number = parsed.get("card_number")
        name = f"Cartela {card_number}" if card_number else f"Cartela {uuid.uuid4().hex[:6].upper()}"

    marks = [[False for _ in range(5)] for _ in range(5)]
    marks[2][2] = True

    card = BingoCard(
        name=name,
        image_filename=filename,
        source_type="camera",
        player_id=int(player_id) if player_id else None,
        numbers_json="[]",
        marks_json="[]",
        suspicious_json="[]",
        is_winner=False,
    )
    card.numbers = parsed["numbers"]
    card.marks = marks
    card.suspicious = parsed.get("suspicious", [])

    db.session.add(card)
    db.session.commit()

    flash("Cartela capturada. Revise os números e o nome antes de salvar definitivamente.", "warning")
    return redirect(url_for("review_card", card_id=card.id))


@app.route("/card/<int:card_id>/review", methods=["GET", "POST"])
def review_card(card_id):
    card = BingoCard.query.get_or_404(card_id)

    if request.method == "POST":
        new_name = request.form.get("card_name", "").strip()
        if new_name:
            card.name = new_name

        numbers = []
        suspicious = []

        expected_ranges = {
            0: (1, 15),
            1: (16, 30),
            2: (31, 45),
            3: (46, 60),
            4: (61, 75),
        }

        for r in range(5):
            row = []
            for c in range(5):
                if r == 2 and c == 2:
                    row.append(0)
                    continue

                field = f"cell_{r}_{c}"
                value = request.form.get(field, "0").strip()

                try:
                    n = int(value)
                except ValueError:
                    n = 0

                row.append(n)

                lo, hi = expected_ranges[c]
                if not (lo <= n <= hi):
                    suspicious.append({"row": r, "col": c})

            numbers.append(row)

        card.numbers = numbers
        card.suspicious = suspicious
        db.session.commit()

        flash("Cartela revisada e salva.", "success")
        return redirect(url_for("game"))

    image_url = url_for("uploaded_file", filename=card.image_filename)
    return render_template("review_card.html", card=card, image_url=image_url)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/game")
def game():
    cards = BingoCard.query.order_by(BingoCard.id.asc()).all()
    state = GameState.get_singleton()
    return render_template("game.html", cards=cards, state=state)


@app.route("/set-pattern", methods=["POST"])
def set_pattern():
    pattern = request.form.get("pattern", "quina").strip().lower()
    if pattern not in {"quina", "l", "v"}:
        pattern = "quina"

    state = GameState.get_singleton()
    state.current_pattern = pattern
    db.session.commit()

    flash(f"Padrão atual: {pattern.upper()}", "info")
    return redirect(url_for("game"))


@app.route("/new-game", methods=["POST"])
def new_game():
    state = GameState.get_singleton()
    state.drawn_numbers = []
    state.winners = []
    state.current_pattern = request.form.get("pattern", state.current_pattern).strip().lower()

    cards = BingoCard.query.all()
    for card in cards:
        card.reset_marks()

    db.session.commit()
    flash("Novo jogo iniciado.", "success")
    return redirect(url_for("game"))


@app.route("/draw-number", methods=["POST"])
def draw_number():
    global LAST_NUMBER_SUBMISSION

    raw_value = request.form.get("value", "").strip()
    number = parse_bingo_input(raw_value)

    if number is None:
        return jsonify({"ok": False, "message": "Número inválido."}), 400

    now = time.time()
    if LAST_NUMBER_SUBMISSION["value"] == number and (now - LAST_NUMBER_SUBMISSION["time"]) < 1.5:
        return jsonify({"ok": False, "message": f"O número {number} acabou de ser enviado."}), 400

    LAST_NUMBER_SUBMISSION["value"] = number
    LAST_NUMBER_SUBMISSION["time"] = now

    state = GameState.get_singleton()
    drawn = state.drawn_numbers

    if number in drawn:
        return jsonify({"ok": False, "message": f"O número {number} já foi sorteado."}), 400

    drawn.append(number)
    state.drawn_numbers = drawn

    cards = BingoCard.query.order_by(BingoCard.id.asc()).all()
    winners = []

    for card in cards:
        card.mark_number(number)
        if has_bingo(card.marks, state.current_pattern):
            card.is_winner = True
            player_name = card.player.name if card.player else None
            winners.append({
                "id": card.id,
                "name": card.name,
                "player": player_name,
            })

    state.winners = winners
    db.session.commit()

    cards_payload = []
    for card in cards:
        cards_payload.append({
            "id": card.id,
            "name": card.name,
            "player": card.player.name if card.player else None,
            "numbers": card.numbers,
            "marks": card.marks,
            "is_winner": card.is_winner,
        })

    return jsonify({
        "ok": True,
        "number": number,
        "pattern": state.current_pattern,
        "drawn_numbers": state.drawn_numbers,
        "winners": winners,
        "cards": cards_payload,
    })


@app.route("/delete-card/<int:card_id>", methods=["POST"])
def delete_card(card_id):
    card = BingoCard.query.get_or_404(card_id)

    if card.image_filename:
        path = os.path.join(app.config["UPLOAD_FOLDER"], card.image_filename)
        if os.path.exists(path):
            os.remove(path)

    db.session.delete(card)
    db.session.commit()
    flash("Cartela removida.", "info")
    return redirect(url_for("index"))


@app.route("/api/cards")
def api_cards():
    cards = BingoCard.query.order_by(BingoCard.id.asc()).all()
    data = []
    for card in cards:
        data.append({
            "id": card.id,
            "name": card.name,
            "player": card.player.name if card.player else None,
            "numbers": card.numbers,
            "marks": card.marks,
            "is_winner": card.is_winner,
        })
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
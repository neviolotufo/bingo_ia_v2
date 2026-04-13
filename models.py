import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cards = db.relationship("BingoCard", backref="player", lazy=True, cascade="all, delete-orphan")


class BingoCard(db.Model):
    __tablename__ = "bingo_cards"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    source_type = db.Column(db.String(30), default="upload")

    numbers_json = db.Column(db.Text, nullable=False)
    marks_json = db.Column(db.Text, nullable=False)
    suspicious_json = db.Column(db.Text, nullable=False, default="[]")

    is_winner = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def numbers(self):
        return json.loads(self.numbers_json)

    @numbers.setter
    def numbers(self, value):
        self.numbers_json = json.dumps(value, ensure_ascii=False)

    @property
    def marks(self):
        return json.loads(self.marks_json)

    @marks.setter
    def marks(self, value):
        self.marks_json = json.dumps(value, ensure_ascii=False)

    @property
    def suspicious(self):
        return json.loads(self.suspicious_json or "[]")

    @suspicious.setter
    def suspicious(self, value):
        self.suspicious_json = json.dumps(value, ensure_ascii=False)

    def reset_marks(self):
        marks = [[False for _ in range(5)] for _ in range(5)]
        marks[2][2] = True
        self.marks = marks
        self.is_winner = False

    def mark_number(self, number: int):
        numbers = self.numbers
        marks = self.marks

        for r in range(5):
            for c in range(5):
                if r == 2 and c == 2:
                    marks[r][c] = True
                    continue
                if numbers[r][c] == number:
                    marks[r][c] = True

        self.marks = marks


class GameState(db.Model):
    __tablename__ = "game_state"

    id = db.Column(db.Integer, primary_key=True)
    current_pattern = db.Column(db.String(20), default="quina")
    drawn_numbers_json = db.Column(db.Text, default="[]")
    winners_json = db.Column(db.Text, default="[]")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def drawn_numbers(self):
        return json.loads(self.drawn_numbers_json or "[]")

    @drawn_numbers.setter
    def drawn_numbers(self, value):
        self.drawn_numbers_json = json.dumps(value, ensure_ascii=False)

    @property
    def winners(self):
        return json.loads(self.winners_json or "[]")

    @winners.setter
    def winners(self, value):
        self.winners_json = json.dumps(value, ensure_ascii=False)

    @staticmethod
    def get_singleton():
        state = GameState.query.first()
        if not state:
            state = GameState(current_pattern="quina", drawn_numbers_json="[]", winners_json="[]")
            db.session.add(state)
            db.session.commit()
        return state
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "bingo-ia-v2-secret")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "bingo_v2.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    CACHE_FOLDER = os.path.join(BASE_DIR, "cache")

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    # Ajuste no Windows, se necessário:
    # r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    TESSERACT_CMD = os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
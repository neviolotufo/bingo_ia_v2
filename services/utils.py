import base64
import hashlib
import os
import uuid


def allowed_file(filename, allowed_exts):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_exts


def ensure_dirs(*paths):
    for path in paths:
        os.makedirs(path, exist_ok=True)


def save_base64_image(data_url, upload_folder, ext="jpg"):
    if "," not in data_url:
        raise ValueError("Imagem base64 inválida.")

    header, encoded = data_url.split(",", 1)
    binary = base64.b64decode(encoded)

    filename = f"camera_{uuid.uuid4().hex}.{ext}"
    path = os.path.join(upload_folder, filename)

    with open(path, "wb") as f:
        f.write(binary)

    return filename, path


def file_sha1(path):
    sha1 = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha1.update(chunk)
    return sha1.hexdigest()
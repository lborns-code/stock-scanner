"""
Home Item Visualizer — מעלים תמונת בית + תמונת פריט (קרמיקה, ריצוף, גדר וכו')
והמערכת יוצרת הדמיה פוטוריאליסטית של הפריט בתוך התמונה, תוך שמירה על המראה
המדויק (צבע/מרקם/דוגמה) של הפריט שהועלה.

משתמש במודל עריכת התמונות של גוגל (Gemini "Nano Banana"), שמיועד בדיוק
למשימה הזו: שילוב אובייקט אמיתי מתמונה אחת בתוך תמונה אחרת.
"""

import logging
import mimetypes
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for
from google import genai
from google.genai import types

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
RESULT_DIR = BASE_DIR / "static" / "results"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = 12
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MODEL_NAME = "gemini-2.5-flash-image"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("home_visualizer")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage) -> Path:
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    name = f"{uuid.uuid4().hex}.{ext}"
    path = UPLOAD_DIR / name
    file_storage.save(path)
    return path


def build_prompt(item_label: str, placement: str) -> str:
    item_label = item_label.strip() or "the item"
    prompt = (
        f"You are given two images. The first image is a photo of a house, exterior wall or room. "
        f"The second image shows {item_label} — treat it as a real reference object/material with its "
        f"exact texture, color and pattern. Edit the first image by realistically adding the exact "
        f"object/material from the second image into the scene. Preserve its true colors, texture and "
        f"pattern — do not invent a different design or color. Match the perspective, scale, lighting, "
        f"shadows and reflections of the first image so the final result looks like a single real, "
        f"photorealistic photograph. Keep everything else in the first image unchanged."
    )
    if placement.strip():
        prompt += f" Placement instructions: {placement.strip()}."
    return prompt


def generate_composite(house_path: Path, item_path: Path, item_label: str, placement: str) -> bytes:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY לא מוגדר. הוסף אותו לקובץ .env בתוך home_visualizer/")

    client = genai.Client(api_key=api_key)

    def load_part(path: Path) -> types.Part:
        mime, _ = mimetypes.guess_type(str(path))
        data = path.read_bytes()
        return types.Part.from_bytes(data=data, mime_type=mime or "image/jpeg")

    prompt = build_prompt(item_label, placement)
    contents = [prompt, load_part(house_path), load_part(item_path)]

    response = client.models.generate_content(model=MODEL_NAME, contents=contents)

    candidates = response.candidates or []
    if not candidates or not candidates[0].content or not candidates[0].content.parts:
        raise RuntimeError("המודל לא החזיר תוצאה. נסה שוב או נסח מחדש את התיאור.")

    for part in candidates[0].content.parts:
        if getattr(part, "inline_data", None) is not None:
            return part.inline_data.data

    raise RuntimeError("המודל לא החזיר תמונה. נסה שוב או שנה את התיאור.")


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    house_file = request.files.get("house_image")
    item_file = request.files.get("item_image")
    item_label = request.form.get("item_label", "")
    placement = request.form.get("placement", "")

    error = None
    result_url = None

    if not house_file or house_file.filename == "":
        error = "יש להעלות תמונת בית."
    elif not item_file or item_file.filename == "":
        error = "יש להעלות תמונת פריט (למשל קרמיקה)."
    elif not allowed_file(house_file.filename) or not allowed_file(item_file.filename):
        error = "פורמט קובץ לא נתמך. השתמש ב-PNG, JPG או WEBP."

    house_path = item_path = None
    if not error:
        try:
            house_path = save_upload(house_file)
            item_path = save_upload(item_file)
            image_bytes = generate_composite(house_path, item_path, item_label, placement)

            result_name = f"{uuid.uuid4().hex}.png"
            (RESULT_DIR / result_name).write_bytes(image_bytes)
            result_url = url_for("static", filename=f"results/{result_name}")
        except Exception as exc:
            logger.exception("שגיאה ביצירת ההדמיה")
            error = f"שגיאה ביצירת ההדמיה: {exc}"
        finally:
            for p in (house_path, item_path):
                if p and p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

    return render_template("index.html", error=error, result_url=result_url)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")

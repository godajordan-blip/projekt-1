"""Helyi tanulófelület a szigorú szakoktatói lekérdezéshez."""

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

genai = None
types = None

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8765
MAX_DOC_CHARS = 120_000
MAX_QUESTION_CHARS = 4_000

SZAKKEPZESI_PROMPT = """
Te egy hivatalos magyarországi épületgépészeti (víz-, gáz-, központifűtés- és klímaszerelő) szakoktató vagy.
A feladatod, hogy segítsd a tanulót az elméleti anyag megértésében.
SZIGORÚ SZABÁLYOK:
1. Kizárólag a számodra biztosított dokumentumokból (kontextusból) dolgozhatsz.
2. Ha a kérdésre nincs válasz a dokumentumokban, KÖTELEZŐ kijelentened, hogy az adott információ nem található meg a tananyagban. Tilos külső forrásból vagy saját tudásból kiegészíteni!
3. Nem adhatod ki a modulzáró tesztek pontos kérdéseit vagy válaszait.
4. Magyarázz gyakorlatiasan, építési és szerelési példákon keresztül.
5. Válaszaid végén mindig tegyél fel egy ellenőrző kérdést a tanulónak, hogy meggyőződj az értésről.
"""


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def ensure_sdk() -> None:
    global genai, types
    if genai is not None and types is not None:
        return
    try:
        from google import genai as genai_mod
        from google.genai import types as types_mod
    except ImportError as error:
        raise ValueError(
            "A google-genai csomag nincs telepítve. Futtasd: pip install -r requirements.txt"
        ) from error
    genai = genai_mod
    types = types_mod


def query_ai_instructor(system_instruction: str, context_docs: list, user_question: str) -> str:
    """
    Lekérdezést indít a Gemini modell felé a megadott szigorú kontextusban.
    """
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.2,  # Alacsony hőmérséklet a pontos, tényalapú válaszokért
        top_p=0.95,
    )
    model_name = "gemini-2.5-pro"
    contents = context_docs + [user_question]
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=config,
    )
    return response.text


class InstructorHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/kerdes":
            self._send_json(404, {"error": "Ismeretlen végpont."})
            return
        try:
            payload = self._read_json()
            answer = self._answer(payload)
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return
        except Exception as error:
            self._send_json(502, {"error": f"A modell válasza nem érkezett meg: {error}"})
            return
        self._send_json(200, {"answer": answer})

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2_000_000:
            raise ValueError("A kérés üres vagy túl nagy.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("A kérés nem érvényes JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("A kérés formátuma hibás.")
        return payload

    def _answer(self, payload: dict) -> str:
        question = str(payload.get("user_question", "")).strip()
        if not question:
            raise ValueError("Írj be egy kérdést.")
        if len(question) > MAX_QUESTION_CHARS:
            raise ValueError("A kérdés túl hosszú.")

        docs = payload.get("context_docs", [])
        if isinstance(docs, str):
            docs = [docs]
        if not isinstance(docs, list) or not docs:
            raise ValueError("Illeszd be a tananyag szövegét.")
        context_docs = []
        for item in docs:
            text = str(item).strip()
            if text:
                context_docs.append(text)
        if not context_docs:
            raise ValueError("Illeszd be a tananyag szövegét.")
        if sum(len(text) for text in context_docs) > MAX_DOC_CHARS:
            raise ValueError("A tananyag túl hosszú ehhez a helyi felülethez.")

        api_key = str(payload.get("api_key", "")).strip() or os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Hiányzik a Gemini API-kulcs. Add meg a mezőben, vagy a .env fájlban.")

        ensure_sdk()
        global client
        client = genai.Client(api_key=api_key)
        answer = query_ai_instructor(SZAKKEPZESI_PROMPT, context_docs, question)
        if not answer or not str(answer).strip():
            raise ValueError("A modell üres választ adott.")
        return str(answer).strip()

    def _send_json(self, status: int, body: dict) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))


def main() -> None:
    load_env_file(ROOT / ".env")
    server = ThreadingHTTPServer((HOST, PORT), InstructorHandler)
    print(f"Szakoktató: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

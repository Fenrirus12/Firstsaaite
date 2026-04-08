from __future__ import annotations

import base64
import json
import mimetypes
import os
from datetime import date, datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = ROOT_DIR / "data"
REQUESTS_FILE = DATA_DIR / "requests.json"
REVIEWS_FILE = DATA_DIR / "reviews.json"
MAX_REQUEST_SIZE = 32 * 1024
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-please")


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for file_path, default in (
        (REQUESTS_FILE, "[]"),
        (REVIEWS_FILE, "[]"),
    ):
        if not file_path.exists():
            file_path.write_text(default, encoding="utf-8")


def load_json_list(file_path: Path) -> list[dict]:
    ensure_storage()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        file_path.write_text("[]", encoding="utf-8")
        return []
    return data if isinstance(data, list) else []


def write_json_list(file_path: Path, entries: list[dict]) -> None:
    file_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_requests() -> list[dict]:
    return load_json_list(REQUESTS_FILE)


def write_requests(entries: list[dict]) -> None:
    write_json_list(REQUESTS_FILE, entries)


def load_reviews() -> list[dict]:
    return load_json_list(REVIEWS_FILE)


def write_reviews(entries: list[dict]) -> None:
    write_json_list(REVIEWS_FILE, entries)


def next_id(entries: list[dict]) -> int:
    return max((int(item.get("id", 0)) for item in entries), default=0) + 1


def save_request(payload: dict) -> dict:
    entries = load_requests()
    record = {
        "id": next_id(entries),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    entries.append(record)
    write_requests(entries)
    return record


def save_review(payload: dict) -> dict:
    entries = load_reviews()
    record = {
        "id": next_id(entries),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        **payload,
    }
    entries.append(record)
    write_reviews(entries)
    return record


def delete_request(request_id: int) -> dict | None:
    entries = load_requests()
    remaining: list[dict] = []
    deleted: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) == request_id and deleted is None:
            deleted = item
            continue
        remaining.append(item)

    if deleted is None:
        return None

    write_requests(remaining)
    return deleted


def update_review_status(review_id: int, status: str) -> dict | None:
    entries = load_reviews()
    updated: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) != review_id:
            continue
        item["status"] = status
        item["moderatedAt"] = datetime.now(timezone.utc).isoformat()
        updated = item
        break

    if updated is None:
        return None

    write_reviews(entries)
    return updated


def update_review(review_id: int, payload: dict) -> dict | None:
    entries = load_reviews()
    updated: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) != review_id:
            continue
        item["name"] = payload["name"]
        item["role"] = payload["role"]
        item["text"] = payload["text"]
        item["updatedAt"] = datetime.now(timezone.utc).isoformat()
        updated = item
        break

    if updated is None:
        return None

    write_reviews(entries)
    return updated


def delete_review(review_id: int) -> dict | None:
    entries = load_reviews()
    remaining: list[dict] = []
    deleted: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) == review_id and deleted is None:
            deleted = item
            continue
        remaining.append(item)

    if deleted is None:
        return None

    write_reviews(remaining)
    return deleted


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def safe_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date() if value else None
    except ValueError:
        return None


def matches_request_filters(item: dict, query: str, task_type: str, date_from: date | None, date_to: date | None) -> bool:
    created_at = safe_date(str(item.get("createdAt", "")))
    if date_from and (created_at is None or created_at < date_from):
        return False
    if date_to and (created_at is None or created_at > date_to):
        return False
    if task_type and str(item.get("taskType", "")).strip().lower() != task_type.strip().lower():
        return False
    if query:
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("name", "contact", "taskType", "deadline", "details")
        ).lower()
        if query.lower() not in haystack:
            return False
    return True


def matches_review_filters(item: dict, query: str, status: str) -> bool:
    if status and str(item.get("status", "")).strip().lower() != status.strip().lower():
        return False
    if query:
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("name", "role", "text")
        ).lower()
        if query.lower() not in haystack:
            return False
    return True


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ProsePrincessClone/1.3"

    def do_GET(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/requests":
            self._require_admin()
            if self._response_sent:
                return
            params = parse_qs(parsed.query)
            items = self._filter_requests(params)
            self._send_json({"ok": True, "items": items})
            return

        if parsed.path == "/api/reviews":
            approved = [
                item
                for item in reversed(load_reviews())
                if str(item.get("status", "")) == "approved"
            ]
            self._send_json({"ok": True, "items": approved})
            return

        if parsed.path == "/api/admin/reviews":
            self._require_admin()
            if self._response_sent:
                return
            params = parse_qs(parsed.query)
            items = self._filter_reviews(params)
            self._send_json({"ok": True, "items": items})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)

        if parsed.path == "/api/requests":
            payload = self._read_json_body()
            if payload is None:
                return
            errors = self._validate_request(payload)
            if errors:
                self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                return
            record = save_request(payload)
            self._send_json(
                {
                    "ok": True,
                    "message": "Заявка отправлена. Я свяжусь с вами в ближайшее время.",
                    "requestId": record["id"],
                },
                status=HTTPStatus.CREATED,
            )
            return

        if parsed.path == "/api/reviews":
            payload = self._read_json_body()
            if payload is None:
                return
            errors = self._validate_review(payload)
            if errors:
                self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                return
            record = save_review(payload)
            self._send_json(
                {
                    "ok": True,
                    "message": "Отзыв отправлен и ждёт одобрения администратора.",
                    "reviewId": record["id"],
                },
                status=HTTPStatus.CREATED,
            )
            return

        if parsed.path.startswith("/api/admin/reviews/") and parsed.path.endswith("/approve"):
            self._change_review_status(parsed.path, "approved")
            return

        if parsed.path.startswith("/api/admin/reviews/") and parsed.path.endswith("/reject"):
            self._change_review_status(parsed.path, "rejected")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_DELETE(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/admin/reviews/"):
            self._require_admin()
            if self._response_sent:
                return

            review_id_raw = parsed.path.removeprefix("/api/admin/reviews/").strip("/")
            if not review_id_raw.isdigit():
                self._send_json({"ok": False, "message": "Некорректный идентификатор отзыва."}, status=HTTPStatus.BAD_REQUEST)
                return

            deleted = delete_review(int(review_id_raw))
            if deleted is None:
                self._send_json({"ok": False, "message": "Отзыв не найден."}, status=HTTPStatus.NOT_FOUND)
                return

            self._send_json({"ok": True, "message": f"Отзыв #{review_id_raw} удалён."})
            return

        if not parsed.path.startswith("/api/requests/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")
            return

        self._require_admin()
        if self._response_sent:
            return

        request_id_raw = parsed.path.removeprefix("/api/requests/").strip("/")
        if not request_id_raw.isdigit():
            self._send_json({"ok": False, "message": "Некорректный идентификатор заявки."}, status=HTTPStatus.BAD_REQUEST)
            return

        deleted = delete_request(int(request_id_raw))
        if deleted is None:
            self._send_json({"ok": False, "message": "Заявка не найдена."}, status=HTTPStatus.NOT_FOUND)
            return

        self._send_json({"ok": True, "message": f"Заявка #{request_id_raw} удалена."})

    def do_PUT(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/admin/reviews/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")
            return

        self._require_admin()
        if self._response_sent:
            return

        review_id_raw = parsed.path.removeprefix("/api/admin/reviews/").strip("/")
        if not review_id_raw.isdigit():
            self._send_json({"ok": False, "message": "Некорректный идентификатор отзыва."}, status=HTTPStatus.BAD_REQUEST)
            return

        payload = self._read_json_body()
        if payload is None:
            return

        errors = self._validate_review(payload)
        if errors:
            self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
            return

        updated = update_review(int(review_id_raw), payload)
        if updated is None:
            self._send_json({"ok": False, "message": "Отзыв не найден."}, status=HTTPStatus.NOT_FOUND)
            return

        self._send_json({"ok": True, "message": f"Отзыв #{review_id_raw} сохранён.", "item": updated})

    @property
    def _response_sent(self) -> bool:
        return getattr(self, "__response_sent", False)

    @_response_sent.setter
    def _response_sent(self, value: bool) -> None:
        self.__response_sent = value

    def _filter_requests(self, params: dict[str, list[str]]) -> list[dict]:
        query = params.get("q", [""])[0].strip()
        task_type = params.get("taskType", [""])[0].strip()
        date_from = parse_iso_date(params.get("dateFrom", [""])[0].strip()) if params.get("dateFrom") else None
        date_to = parse_iso_date(params.get("dateTo", [""])[0].strip()) if params.get("dateTo") else None
        return [
            item
            for item in reversed(load_requests())
            if matches_request_filters(item, query, task_type, date_from, date_to)
        ]

    def _filter_reviews(self, params: dict[str, list[str]]) -> list[dict]:
        query = params.get("q", [""])[0].strip()
        status = params.get("status", [""])[0].strip()
        return [
            item
            for item in reversed(load_reviews())
            if matches_review_filters(item, query, status)
        ]

    def _read_json_body(self) -> dict | None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_SIZE:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid request size")
            self._response_sent = True
            return None
        try:
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            self._response_sent = True
            return None
        if not isinstance(payload, dict):
            self._send_json({"ok": False, "message": "Ожидался JSON-объект."}, status=HTTPStatus.BAD_REQUEST)
            return None
        return payload

    def _change_review_status(self, path: str, status: str) -> None:
        self._require_admin()
        if self._response_sent:
            return
        review_id_raw = (
            path.removeprefix("/api/admin/reviews/")
            .removesuffix("/approve")
            .removesuffix("/reject")
            .strip("/")
        )
        if not review_id_raw.isdigit():
            self._send_json({"ok": False, "message": "Некорректный идентификатор отзыва."}, status=HTTPStatus.BAD_REQUEST)
            return
        updated = update_review_status(int(review_id_raw), status)
        if updated is None:
            self._send_json({"ok": False, "message": "Отзыв не найден."}, status=HTTPStatus.NOT_FOUND)
            return
        verb = "одобрен" if status == "approved" else "отклонён"
        self._send_json({"ok": True, "message": f"Отзыв #{review_id_raw} {verb}."})

    def _require_admin(self) -> None:
        if self._is_authorized():
            return
        self._send_auth_required()

    def _is_authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        token = header.removeprefix("Basic ").strip()
        try:
            decoded = base64.b64decode(token).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, separator, password = decoded.partition(":")
        return bool(separator) and username == ADMIN_USERNAME and password == ADMIN_PASSWORD

    def _send_auth_required(self) -> None:
        body = json.dumps(
            {"ok": False, "message": "Требуется авторизация для доступа к админ-панели."},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("WWW-Authenticate", 'Basic realm="Admin Panel"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._response_sent = True

    def _validate_request(self, payload: dict) -> dict[str, str]:
        required_fields = {
            "name": "Укажите имя.",
            "contact": "Укажите способ связи.",
            "taskType": "Выберите тип работы.",
            "deadline": "Укажите срок.",
            "details": "Опишите задачу.",
        }
        errors: dict[str, str] = {}
        for field, message in required_fields.items():
            value = payload.get(field, "")
            if not isinstance(value, str) or not value.strip():
                errors[field] = message
        details = str(payload.get("details", ""))
        if details and len(details.strip()) < 20:
            errors["details"] = "Опишите задачу чуть подробнее, минимум 20 символов."
        return errors

    def _validate_review(self, payload: dict) -> dict[str, str]:
        required_fields = {
            "name": "Укажите имя.",
            "role": "Укажите, кто вы или на каком направлении учитесь.",
            "text": "Напишите отзыв.",
        }
        errors: dict[str, str] = {}
        for field, message in required_fields.items():
            value = payload.get(field, "")
            if not isinstance(value, str) or not value.strip():
                errors[field] = message
        text = str(payload.get("text", ""))
        if text and len(text.strip()) < 30:
            errors["text"] = "Отзыв должен быть чуть подробнее, минимум 30 символов."
        return errors

    def _serve_static(self, raw_path: str) -> None:
        routes = {
            "/": "/index.html",
            "/admin": "/admin.html",
        }
        requested = routes.get(raw_path.rstrip("/") or "/", raw_path.rstrip("/") or "/index.html")
        file_path = (STATIC_DIR / requested.lstrip("/")).resolve()
        if STATIC_DIR not in file_path.parents and file_path != STATIC_DIR:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            self._response_sent = True
            return
        if not file_path.exists() or not file_path.is_file():
            file_path = STATIC_DIR / "index.html"
        try:
            content = file_path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to read file")
            self._response_sent = True
            return
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        self._response_sent = True

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._response_sent = True

    def log_message(self, format: str, *args: object) -> None:
        return


def run() -> None:
    ensure_storage()
    host = "127.0.0.1"
    port = 8000
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Server running on http://{host}:{port}")
    print(f"Admin panel: http://{host}:{port}/admin")
    print("Set ADMIN_USERNAME and ADMIN_PASSWORD to change admin credentials.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()

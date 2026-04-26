import os
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any, Dict, Iterable, List, Optional

import requests
from dotenv import load_dotenv


KINOPUB_API_BASE = "https://api.service-kp.com"
KINOPUB_WEB_BASE = "https://kino.pub"
TELEGRAM_API_BASE = "https://api.telegram.org"


def get_env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if required and (value is None or not value.strip()):
        raise ValueError(f"Environment variable '{name}' is required.")
    return (value or "").strip()


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        parsed = parse_iso_datetime(value)
        if parsed:
            return parsed
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def item_type(item: Dict[str, Any]) -> str:
    raw = str(item.get("type", "")).lower()
    if "serial" in raw or "series" in raw:
        return "serial"
    if "movie" in raw or "film" in raw:
        return "movie"
    seasons = item.get("seasons")
    return "serial" if seasons else "movie"


def extract_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]  # type: ignore[arg-type]
    return []


def to_text(value: Any, max_len: int = 220) -> str:
    text = unescape(str(value or "")).replace("\n", " ").strip()
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def item_link(item: Dict[str, Any]) -> str:
    slug = item.get("slug")
    item_id = item.get("id")
    if slug:
        return f"{KINOPUB_WEB_BASE}/{slug}"
    if item_id is not None:
        return f"{KINOPUB_WEB_BASE}/item/view/{item_id}"
    return KINOPUB_WEB_BASE


def fetch_recent_items(token: str, days: int = 7) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    params = {
        "sort": "created",
        "perpage": 200,
        "page": 1,
        "from": cutoff.strftime("%Y-%m-%d"),
    }

    response = requests.get(
        f"{KINOPUB_API_BASE}/v1/items",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    items = extract_items(payload)

    recent_items: List[Dict[str, Any]] = []
    for item in items:
        added_at = (
            parse_iso_datetime(item.get("created_at"))
            or parse_date(item.get("created"))
            or parse_date(item.get("updated"))
            or parse_date(item.get("publish_date"))
        )
        if added_at is None:
            # If API does not provide reliable timestamps, keep item and let API-side
            # date filter (`from`) drive recency.
            recent_items.append(item)
            continue
        if added_at.astimezone(timezone.utc) >= cutoff:
            recent_items.append(item)
    return recent_items


def apply_filters(items: Iterable[Dict[str, Any]], filter_year: int, filter_type: str) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for item in items:
        year = item.get("year")
        item_kind = item_type(item)

        if year is not None and str(year).isdigit():
            if int(year) < filter_year:
                continue

        if filter_type != "all" and item_kind != filter_type:
            continue

        filtered.append(item)
    return filtered


def format_message(items: List[Dict[str, Any]]) -> str:
    chunks = []
    for item in items:
        title = to_text(item.get("title") or item.get("name") or "Untitled", max_len=120)
        year = item.get("year") or "N/A"
        rating = item.get("rating") or item.get("imdb_rating") or "N/A"
        description = to_text(
            item.get("short_description")
            or item.get("plot")
            or item.get("description")
            or "No description.",
            max_len=240,
        )
        link = item_link(item)
        chunks.append(
            "\n".join(
                [
                    f"🎬 <b>{title}</b>",
                    f"Year: {year}",
                    f"Rating: {rating}",
                    f"{description}",
                    f"<a href=\"{link}\">Open in kino.pub</a>",
                ]
            )
        )
    return "\n\n" + ("\n\n".join(chunks))


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    response = requests.post(
        f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=30,
    )
    response.raise_for_status()


def main() -> None:
    load_dotenv()

    kinopub_token = get_env("KINOPUB_TOKEN")
    telegram_bot_token = get_env("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = get_env("TELEGRAM_CHAT_ID")
    filter_year_raw = get_env("FILTER_YEAR", required=False, default="1900")
    filter_type = get_env("FILTER_TYPE", required=False, default="all").lower()

    if filter_type not in {"all", "movie", "serial"}:
        raise ValueError("FILTER_TYPE must be one of: all, movie, serial.")

    try:
        filter_year = int(filter_year_raw)
    except ValueError as exc:
        raise ValueError("FILTER_YEAR must be an integer.") from exc

    recent_items = fetch_recent_items(kinopub_token, days=7)
    filtered_items = apply_filters(recent_items, filter_year=filter_year, filter_type=filter_type)

    if not filtered_items:
        return

    message = "🆕 New KinoPub additions:\n" + format_message(filtered_items[:20])
    send_telegram_message(telegram_bot_token, telegram_chat_id, message)


if __name__ == "__main__":
    main()

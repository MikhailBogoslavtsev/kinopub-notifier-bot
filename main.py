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


def item_link(item: Dict[str, Any]) -> str:
    slug = item.get("slug")
    item_id = item.get("id")
    if slug:
        return f"{KINOPUB_WEB_BASE}/{slug}"
    if item_id is not None:
        return f"{KINOPUB_WEB_BASE}/item/view/{item_id}"
    return KINOPUB_WEB_BASE


def to_text(value: Any, max_len: int = 220) -> str:
    text = unescape(str(value or "")).replace("\n", " ").strip()
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


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
    filter_year = int(get_env("FILTER_YEAR", required=False, default="1900"))
    filter_type = get_env("FILTER_TYPE", required=False, default="all").lower()

    print(f"Starting KinoPub notifier...")
    print(f"Filter: year >= {filter_year}, type = {filter_type}")

    # Fetch fresh items
    headers = {"Authorization": f"Bearer {kinopub_token}"}
    params = {"sort": "created-", "perpage": 50, "page": 1}

    response = requests.get(
        f"{KINOPUB_API_BASE}/v1/items",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    items = payload.get("items", [])
    print(f"Fetched {len(items)} items from API")

    if items:
        print(f"First item sample: {items[0]}")

    # Filter
    filtered = []
    for item in items:
        year = item.get("year")
        kind = str(item.get("type", "")).lower()
        imdb = item.get("imdb_rating") or 0

        if year and int(year) < filter_year:
            continue
        if filter_type != "all":
            if filter_type == "serial" and "serial" not in kind:
                continue
            if filter_type == "movie" and "movie" not in kind:
                continue
        if imdb < 6.5:
            continue
        if kind not in ("movie",):
            continue
        filtered.append(item)

    print(f"After filtering: {len(filtered)} items")

    if not filtered:
        print("No items found, nothing to send")
        return

    # Format message
    chunks = []
    for item in filtered[:10]:
        title = to_text(item.get("title") or item.get("name") or "Untitled", max_len=120)
        year = item.get("year") or "N/A"
        rating = item.get("rating") or "N/A"
        description = to_text(item.get("plot") or item.get("description") or "", max_len=200)
        link = item_link(item)
        chunks.append(f"🎬 <b>{title}</b> ({year}) ⭐{rating}\n{description}\n<a href='{link}'>Смотреть</a>")

    message = "🆕 Новинки KinoPub:\n\n" + "\n\n".join(chunks)
    message = message[:4000]  # Telegram limit
    print(f"Sending message with {len(filtered)} items...")
    send_telegram_message(telegram_bot_token, telegram_chat_id, message)
    print("Done!")


if __name__ == "__main__":
    main()

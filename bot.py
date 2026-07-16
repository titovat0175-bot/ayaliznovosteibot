import asyncio
import logging
import os
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from html import unescape

import httpx
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_token() -> str | None:
    # 1) Environment variable (preferred)
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if token:
        return token.strip()

    # 2) .env file in project directory
    env_path = Path(".env")
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key in {"TELEGRAM_BOT_TOKEN", "BOT_TOKEN"} and value:
                return value

    # 3) Plain token file
    token_file = Path("token.txt")
    if token_file.exists():
        value = token_file.read_text(encoding="utf-8").strip()
        if value:
            return value

    return None


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[["Анализ за 12 часов"]],
    resize_keyboard=True,
    one_time_keyboard=False,
    input_field_placeholder="Нажми для автоанализа",
)


CHANNELS = {
    "moscowachBusiness": "@moscowachBusiness",
    "moscowmap": "@moscowmap",
    "msk_live": "@msk_live",
    "xrschoolsyntx": "@xrschoolsyntx",
    "shumim_media": "@shumim_media",
}

TOPIC_RULES = {
    "Экономика и бизнес": ["мосбирж", "рынок", "инвест", "фнс", "маркетплейс", "цб", "ставк", "продаж", "цены", "руб"],
    "Город и транспорт": ["метро", "иволг", "транспорт", "мцд", "поезд", "парковк", "дорог", "станц"],
    "Погода и предупреждения": ["ветер", "гроза", "лив", "шторм", "мчс", "погод", "ураган"],
    "Происшествия и безопасность": ["упал", "чп", "пострадав", "мошен", "полиц", "мвд", "проверк", "авар"],
    "Технологии и digital": ["apple", "iphone", "tiktok", "рилс", "ruStore", "vk", "приложен", "цифров"],
    "Обучение и AI": ["ai", "нейросет", "school", "урок", "курс", "спикер", "обучен"],
    "Шоу и медиа": ["селебр", "тизер", "инстасам", "стример", "вирус", "мем", "шоу"],
}


def strip_html(raw_html: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", raw_html)
    clean = re.sub(r"\s+", " ", unescape(no_tags)).strip()
    return clean


def remove_emoji(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002700-\U000027BF"
        "\U00002600-\U000026FF"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def clean_post_text(text: str) -> str:
    text = remove_emoji(text)
    text = re.sub(r"\bPlease open Telegram to view this post\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bVIEW IN TELEGRAM\b", " ", text, flags=re.IGNORECASE)

    # Remove common promo/subscription fragments.
    promo_patterns = [
        r"подпишит[её]сь[^.?!]*[.?!]?",
        r"подписаться[^.?!]*[.?!]?",
        r"по вопросам рекламы[^.?!]*[.?!]?",
        r"прислать новость[^.?!]*[.?!]?",
        r"сотрудничество[^.?!]*[.?!]?",
        r"ссылка для друзей[^.?!]*[.?!]?",
    ]
    for pattern in promo_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_datetime(raw: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def classify_topic(text: str) -> str:
    lower = text.lower()
    best_topic = "Разное"
    best_score = 0
    for topic, keywords in TOPIC_RULES.items():
        score = sum(1 for kw in keywords if kw.lower() in lower)
        if score > best_score:
            best_score = score
            best_topic = topic
    return best_topic


def extract_posts_from_html(page_html: str, cutoff_utc: datetime) -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    chunks = page_html.split('<div class="tgme_widget_message_wrap')
    for chunk in chunks[1:]:
        block = '<div class="tgme_widget_message_wrap' + chunk
        dt_match = re.search(r'datetime="([^"]+)"', block, flags=re.DOTALL)
        if not dt_match:
            continue
        dt = parse_datetime(dt_match.group(1))
        if not dt or dt < cutoff_utc:
            continue

        text_match = re.search(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>\s*<div class="tgme_widget_message_footer',
            block,
            flags=re.DOTALL,
        )
        if text_match:
            text = clean_post_text(strip_html(text_match.group(1)))
        else:
            # Some posts are media-only. Keep a short placeholder so they are counted.
            text = "Медиа-пост без текстового описания."

        if not text:
            continue
        posts.append({"datetime": dt.isoformat(), "text": text})
    return posts


async def fetch_channel_posts(client: httpx.AsyncClient, channel_id: str, hours: int = 12) -> list[dict[str, str]]:
    url = f"https://t.me/s/{channel_id}"
    response = await client.get(url)
    response.raise_for_status()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return extract_posts_from_html(response.text, cutoff)


def build_channel_summary(channel_name: str, posts: list[dict[str, str]]) -> str:
    if not posts:
        return f"{channel_name}\nНовых постов за последние 12 часов не найдено."

    grouped: dict[str, list[str]] = {}
    for post in posts:
        topic = classify_topic(post["text"])
        grouped.setdefault(topic, []).append(post["text"])

    sorted_topics = sorted(grouped.items(), key=lambda kv: len(kv[1]), reverse=True)[:5]
    lines = [
        channel_name,
        f"Постов за последние 12 часов: {len(posts)}",
        "Выделенные подтемы и факты:",
    ]
    for topic, topic_posts in sorted_topics:
        lines.append(f"- {topic} ({len(topic_posts)} публикации)")
        for sample in topic_posts[:2]:
            snippet = sample[:220].strip()
            if len(sample) > 220:
                snippet += "..."
            lines.append(f"  * {snippet}")
    return "\n".join(lines)


async def build_full_digest(hours: int = 12) -> list[str]:
    timeout = httpx.Timeout(20.0)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        tasks = [fetch_channel_posts(client, channel_id, hours) for channel_id in CHANNELS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    blocks: list[str] = [f"Анализ по заданным каналам за последние {hours} часов."]
    for (channel_id, channel_name), result in zip(CHANNELS.items(), results):
        if isinstance(result, Exception):
            blocks.append(f"{channel_name}\nОшибка чтения канала: {result}")
            continue
        blocks.append(build_channel_summary(channel_name, result))

    return blocks


def split_message(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit and current:
            parts.append(current.rstrip())
            current = line
        else:
            current += line
    if current.strip():
        parts.append(current.rstrip())
    return parts


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Нажмите кнопку ниже. Я соберу развернутую информацию по заданным каналам за 12 часов.",
        reply_markup=MAIN_KEYBOARD,
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip().lower()

    if "анализ" in text or "12" in text:
        await update.message.reply_text("Собираю данные и формирую развернутый отчет по каждому каналу...")
        try:
            blocks = await build_full_digest(hours=12)
        except Exception as exc:
            await update.message.reply_text(f"Не удалось собрать данные: {exc}", reply_markup=MAIN_KEYBOARD)
            return
        for block in blocks:
            for part in split_message(block):
                await update.message.reply_text(part)
        await update.message.reply_text("Отчет завершен.", reply_markup=MAIN_KEYBOARD)
        return

    await update.message.reply_text("Напишите «анализ» или нажмите кнопку.", reply_markup=MAIN_KEYBOARD)


def main() -> None:
    token = load_token()
    if not token:
        raise RuntimeError(
            "Токен не найден.\n"
            "Вариант 1 (на текущую сессию PowerShell):\n"
            "$env:TELEGRAM_BOT_TOKEN='YOUR_TOKEN'\n"
            "Вариант 2: создай .env с TELEGRAM_BOT_TOKEN=YOUR_TOKEN\n"
            "Вариант 3: создай файл token.txt и вставь в него токен."
        )

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    # Python 3.14+: create and set an explicit event loop for compatibility.
    asyncio.set_event_loop(asyncio.new_event_loop())
    logger.info("Bot started. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

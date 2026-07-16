import asyncio
import logging
import os
from typing import Final

from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

TOKEN: Final[str | None] = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "Не найден TELEGRAM_BOT_TOKEN. Создай .env на основе .env.example и укажи токен."
    )

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BTN_TOKEN = "1) Получить токен бота"
BTN_CURSOR = "2) Начало в Cursor"
BTN_GITHUB_START = "3) GitHub: создать репозиторий"
BTN_GITHUB_FILES = "4) GitHub: добавить файлы"
BTN_GITHUB_EDIT = "5) Как менять код в GitHub"
BTN_BOTHOST = "6) Деплой на BotHost"
BTN_ERRORS = "7) Ошибки и важные моменты"
BTN_CHECKLIST = "8) Полный чеклист"
BTN_NAV_HELP = "9) Я запуталась: куда нажимать"
BTN_GH_NAV = "GitHub: где какая кнопка"
BTN_BH_NAV = "BotHost: где что искать"
BTN_FIND_INFO = "Где смотреть логи/токен/файлы"
BTN_NEXT = "Что делать дальше"
BTN_MENU = "Главное меню"


def build_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(BTN_TOKEN), KeyboardButton(BTN_CURSOR)],
        [KeyboardButton(BTN_GITHUB_START), KeyboardButton(BTN_GITHUB_FILES)],
        [KeyboardButton(BTN_GITHUB_EDIT), KeyboardButton(BTN_BOTHOST)],
        [KeyboardButton(BTN_ERRORS), KeyboardButton(BTN_CHECKLIST)],
        [KeyboardButton(BTN_NAV_HELP), KeyboardButton(BTN_NEXT)],
        [KeyboardButton(BTN_GH_NAV), KeyboardButton(BTN_BH_NAV)],
        [KeyboardButton(BTN_FIND_INFO)],
        [KeyboardButton(BTN_MENU)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def instruction_token() -> str:
    return (
        "1) Как получить токен бота в Telegram\n\n"
        "1. Открой Telegram и найди @BotFather.\n"
        "2. Нажми Start.\n"
        "3. Отправь /newbot.\n"
        "4. Укажи имя бота и username (должен заканчиваться на bot).\n"
        "5. Скопируй токен из ответа BotFather.\n\n"
        "Важно:\n"
        "- Токен хранить только в .env.\n"
        "- Если токен случайно кому-то показали, в BotFather используй /revoke."
    )


def instruction_cursor() -> str:
    return (
        "2) С чего начинать в Cursor\n\n"
        "1. Открой Cursor.\n"
        "2. Нажми File -> Open Folder.\n"
        "3. Выбери место и нажми New Folder.\n"
        "4. Назови папку проекта (например: telegram-guide-bot) и открой ее.\n"
        "5. Открой Terminal -> New Terminal.\n"
        "6. В левой панели Explorer нажми New File и создай:\n"
        "   - bot.py\n"
        "   - requirements.txt\n"
        "   - .env.example\n"
        "   - README.md\n\n"
        "Совет: делай изменения маленькими шагами и проверяй запуск после каждого шага."
    )


def instruction_github_start() -> str:
    return (
        "3) GitHub: создать репозиторий\n\n"
        "1. Открой github.com и войди в аккаунт.\n"
        "2. Нажми + (вверху справа) -> New repository.\n"
        "3. Введи имя репозитория.\n"
        "4. Выбери Public или Private.\n"
        "5. Нажми Create repository.\n\n"
        "После этого можно загружать файлы через веб-интерфейс GitHub."
    )


def instruction_github_files() -> str:
    return (
        "4) GitHub: как добавлять файлы (через интерфейс)\n\n"
        "Способ 1: Create new file\n"
        "1. Открой свой репозиторий.\n"
        "2. Нажми Add file -> Create new file.\n"
        "3. Впиши имя файла (например, bot.py).\n"
        "4. Вставь код.\n"
        "5. Нажми Commit changes.\n\n"
        "Способ 2: Upload files\n"
        "1. Открой репозиторий.\n"
        "2. Нажми Add file -> Upload files.\n"
        "3. Перетащи файлы или выбери их через Choose your files.\n"
        "4. Нажми Commit changes.\n\n"
        "Обязательно: файл .env не загружай в репозиторий."
    )


def instruction_github_edit() -> str:
    return (
        "5) Как менять код на GitHub\n\n"
        "1. Открой нужный файл в репозитории.\n"
        "2. Нажми иконку карандаша (Edit this file).\n"
        "3. Измени код.\n"
        "4. Внизу страницы введи описание изменения (Commit message).\n"
        "5. Нажми Commit changes.\n\n"
        "Если нужна проверка перед публикацией:\n"
        "- Выбери Create a new branch for this commit.\n"
        "- Затем создай Pull Request."
    )


def instruction_bothost() -> str:
    return (
        "6) Как добавить бота на сервер BotHost\n\n"
        "Общий сценарий под интерфейс BotHost:\n"
        "1. Войди в аккаунт BotHost.\n"
        "2. Нажми кнопку создания бота/проекта (обычно Add bot или Create bot).\n"
        "3. Выбери запуск через Python.\n"
        "4. Загрузи файлы проекта (bot.py, requirements.txt).\n"
        "5. В разделе переменных окружения добавь:\n"
        "   TELEGRAM_BOT_TOKEN=твой_токен\n"
        "6. Укажи команду запуска: python bot.py (или py bot.py, если так настроено).\n"
        "7. Нажми Save/Deploy/Start.\n"
        "8. Открой Logs и проверь, что есть строка Application started.\n\n"
        "Внимание:\n"
        "- Должен быть запущен только один экземпляр бота.\n"
        "- Токен добавляется только в переменные окружения, не в код."
    )


def instruction_errors() -> str:
    return (
        "7) На что обращать внимание\n\n"
        "- Unauthorized: неверный токен или токен отозван.\n"
        "- Conflict: запущено несколько экземпляров одного бота.\n"
        "- ModuleNotFoundError: не установлены зависимости.\n"
        "- Бот молчит: проверь логи и убедись, что процесс запущен.\n\n"
        "Безопасность:\n"
        "- Никогда не публикуй .env.\n"
        "- Добавь .env в .gitignore."
    )


def instruction_checklist() -> str:
    return (
        "8) Полный чеклист: бот-инструкция для создания других ботов\n\n"
        "1. Получи токен у @BotFather.\n"
        "2. Создай папку проекта и файлы в Cursor.\n"
        "3. Создай репозиторий на GitHub.\n"
        "4. Добавь файлы через Add file -> Create new file / Upload files.\n"
        "5. При изменениях правь файлы через Edit (карандаш) и делай Commit.\n"
        "6. На BotHost создай проект, загрузи файлы и добавь TELEGRAM_BOT_TOKEN.\n"
        "7. Запусти бота и проверь логи.\n"
        "8. При ошибках проверь токен, зависимости и количество запущенных копий."
    )


def instruction_nav_help() -> str:
    return (
        "9) Если запутались: быстрый навигатор\n\n"
        "Выбери кнопку по ситуации:\n"
        f"- {BTN_GH_NAV}\n"
        f"- {BTN_BH_NAV}\n"
        f"- {BTN_FIND_INFO}\n"
        f"- {BTN_NEXT}\n\n"
        "Можно писать и текстом: например 'где на гитхабе upload files?' "
        "или 'где на bothost логи?'."
    )


def instruction_github_nav() -> str:
    return (
        "GitHub: где какая кнопка\n\n"
        "На главной странице репозитория:\n"
        "- Add file -> Create new file: создать новый файл.\n"
        "- Add file -> Upload files: загрузить файлы с компьютера.\n"
        "- Зеленая кнопка Code: скопировать ссылку репозитория.\n"
        "- Вкладка Issues: задачи и обсуждения.\n"
        "- Вкладка Actions: CI и автопроверки.\n"
        "- Вкладка Settings: настройки репозитория.\n\n"
        "Внутри файла:\n"
        "- Карандаш (Edit this file): редактировать.\n"
        "- History: история изменений файла."
    )


def instruction_bothost_nav() -> str:
    return (
        "BotHost: где что искать\n\n"
        "Обычно в интерфейсе BotHost:\n"
        "- Dashboard/Мои боты: список всех проектов.\n"
        "- Add bot/Create bot: создать новый проект.\n"
        "- Files: загрузка/замена bot.py и requirements.txt.\n"
        "- Environment/Variables: добавить TELEGRAM_BOT_TOKEN.\n"
        "- Start/Stop/Restart: управление запуском.\n"
        "- Logs: журнал ошибок и сообщений запуска.\n\n"
        "Если не видишь раздел, открой карточку нужного бота в Dashboard."
    )


def instruction_find_info() -> str:
    return (
        "Где искать нужную информацию\n\n"
        "Токен:\n"
        "- В Telegram у @BotFather, команда /mybots.\n\n"
        "Логи ошибок:\n"
        "- Локально: терминал Cursor, где запущен bot.py.\n"
        "- На сервере: раздел Logs в BotHost.\n\n"
        "Файлы проекта:\n"
        "- В Cursor слева Explorer.\n"
        "- На GitHub в списке файлов репозитория.\n\n"
        "Почему бот не отвечает:\n"
        "- Проверь, запущен ли один экземпляр бота.\n"
        "- Проверь токен и последние строки в Logs."
    )


def instruction_next_step() -> str:
    return (
        "Что делать дальше (если не понимаете следующий шаг)\n\n"
        "1. Нажми '8) Полный чеклист'.\n"
        "2. Выполни только 1 пункт чеклиста.\n"
        "3. Проверь результат (бот отвечает / лог без ошибок).\n"
        "4. Только потом переходи к следующему пункту.\n\n"
        "Если появилась ошибка: открой '7) Ошибки и важные моменты' "
        "и раздел с логами."
    )


async def send_instruction(update: Update, text: str) -> None:
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=build_main_keyboard(),
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name if update.effective_user else "друг"
    if update.message:
        await update.message.reply_text(
            f"Привет, {user_name}!\n"
            "Я бот-инструкция по созданию Telegram-ботов.\n\n"
            "Выбирай раздел кнопками ниже.",
            reply_markup=build_main_keyboard(),
        )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    lower_text = text.casefold()

    if text == BTN_TOKEN:
        await send_instruction(update, instruction_token())
    elif text == BTN_CURSOR:
        await send_instruction(update, instruction_cursor())
    elif text == BTN_GITHUB_START:
        await send_instruction(update, instruction_github_start())
    elif text == BTN_GITHUB_FILES:
        await send_instruction(update, instruction_github_files())
    elif text == BTN_GITHUB_EDIT:
        await send_instruction(update, instruction_github_edit())
    elif text == BTN_BOTHOST:
        await send_instruction(update, instruction_bothost())
    elif text == BTN_ERRORS:
        await send_instruction(update, instruction_errors())
    elif text == BTN_CHECKLIST:
        await send_instruction(update, instruction_checklist())
    elif text == BTN_NAV_HELP:
        await send_instruction(update, instruction_nav_help())
    elif text == BTN_GH_NAV:
        await send_instruction(update, instruction_github_nav())
    elif text == BTN_BH_NAV:
        await send_instruction(update, instruction_bothost_nav())
    elif text == BTN_FIND_INFO:
        await send_instruction(update, instruction_find_info())
    elif text == BTN_NEXT:
        await send_instruction(update, instruction_next_step())
    elif text == BTN_MENU:
        await start(update, context)
    elif "github" in lower_text or "гитхаб" in lower_text:
        await send_instruction(update, instruction_github_nav())
    elif "bothost" in lower_text or "ботхост" in lower_text:
        await send_instruction(update, instruction_bothost_nav())
    elif "логи" in lower_text or "log" in lower_text:
        await send_instruction(update, instruction_find_info())
    elif "куда нажимать" in lower_text or "запут" in lower_text:
        await send_instruction(update, instruction_nav_help())
    else:
        await update.message.reply_text(
            "Если запутались, нажми '9) Я запуталась: куда нажимать' или "
            "напиши, что именно ищешь (GitHub, BotHost, логи, токен).",
            reply_markup=build_main_keyboard(),
        )


def main() -> None:
    # Python 3.14+ может не иметь текущий loop по умолчанию.
    asyncio.set_event_loop(asyncio.new_event_loop())

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

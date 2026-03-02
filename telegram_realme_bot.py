import json
import os
from typing import Any, Dict, List, Tuple

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Set your token in environment variable before running:
# PowerShell: $env:TELEGRAM_BOT_TOKEN="123456:ABC..."
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# In-memory storage for uploaded rows
DATA: List[Dict[str, str]] = []
LAST_FILE_NAME: str = ""

ALLOWED_KEYS = {"market_model", "project_no", "filename"}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _rows_from_json(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    if isinstance(raw, dict):
        # Preferred shape: {"realmeLinks": [...]}
        if isinstance(raw.get("realmeLinks"), list):
            return [x for x in raw["realmeLinks"] if isinstance(x, dict)]

        # Fallback: first list value in dict
        for v in raw.values():
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]

    return []


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in rows:
        out.append(
            {
                "market_model": _norm(r.get("market_model")),
                "project_no": _norm(r.get("project_no")),
                "filename": _norm(r.get("filename")),
                "link": _norm(r.get("link")),
            }
        )
    return out


def _parse_search_args(args: List[str]) -> Tuple[Dict[str, str], List[str]]:
    field_filters: Dict[str, str] = {}
    free_terms: List[str] = []

    for arg in args:
        token = arg.strip()
        if not token:
            continue

        if "=" in token:
            k, v = token.split("=", 1)
            key = k.strip().lower()
            val = v.strip().lower()
            if key in ALLOWED_KEYS and val:
                field_filters[key] = val
            continue

        free_terms.append(token.lower())

    return field_filters, free_terms


def _match_record(record: Dict[str, str], field_filters: Dict[str, str], free_terms: List[str]) -> bool:
    mm = record.get("market_model", "").lower()
    pn = record.get("project_no", "").lower()
    fn = record.get("filename", "").lower()

    if "market_model" in field_filters and field_filters["market_model"] not in mm:
        return False
    if "project_no" in field_filters and field_filters["project_no"] not in pn:
        return False
    if "filename" in field_filters and field_filters["filename"] not in fn:
        return False

    # Free terms can match any searchable field
    hay = f"{mm} {pn} {fn}"
    for t in free_terms:
        if t not in hay:
            return False

    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Upload nooworkfuck.json as document.\n"
        "Then search with either format:\n"
        "/search market_model=RMX5210 project_no=22667 filename=16.0\n"
        "/search rmx5210 22667\n\n"
        "Commands: /start /search /count"
    )


async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not DATA:
        await update.message.reply_text("No data loaded.")
        return
    await update.message.reply_text(f"Loaded records: {len(DATA)} (source: {LAST_FILE_NAME})")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global DATA, LAST_FILE_NAME

    doc = update.message.document
    if not doc:
        return

    if not doc.file_name.lower().endswith(".json"):
        await update.message.reply_text("Please upload a .json file (nooworkfuck.json).")
        return

    tg_file = await context.bot.get_file(doc.file_id)
    local_path = os.path.join(os.getcwd(), "uploaded_nooworkfuck.json")
    await tg_file.download_to_drive(local_path)

    try:
        with open(local_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        rows = _rows_from_json(raw)
        normalized = _normalize_rows(rows)

        if not normalized:
            await update.message.reply_text("No valid rows found in JSON.")
            return

        DATA = normalized
        LAST_FILE_NAME = doc.file_name
        await update.message.reply_text(f"Loaded {len(DATA)} rows from {doc.file_name}.")
        await update.message.reply_text("Thanks For Choosing RELAX TOOL -")
    except Exception as exc:
        await update.message.reply_text(f"Failed to parse JSON: {exc}")


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not DATA:
        await update.message.reply_text("No data loaded. Upload nooworkfuck.json first.")
        return

    field_filters, free_terms = _parse_search_args(context.args)
    if not field_filters and not free_terms:
        await update.message.reply_text(
            "Usage:\n"
            "/search market_model=RMX5210 project_no=22667\n"
            "or\n"
            "/search rmx5210 22667"
        )
        return

    matches = [r for r in DATA if _match_record(r, field_filters, free_terms)]
    if not matches:
        await update.message.reply_text("No match found.")
        return

    # Telegram message limit is 4096 chars; chunk replies.
    lines: List[str] = []
    for i, r in enumerate(matches, 1):
        lines.append(
            f"{i}) {r.get('market_model','')} | {r.get('project_no','')} | {r.get('filename','')}\n{r.get('link','')}"
        )

    current = ""
    sent = 0
    for block in lines:
        next_chunk = (current + "\n\n" + block).strip() if current else block
        if len(next_chunk) > 3900:
            await update.message.reply_text(current)
            sent += current.count("\n\n") + 1
            current = block
        else:
            current = next_chunk

    if current:
        await update.message.reply_text(current)

    if len(matches) > 50:
        await update.message.reply_text(f"Total matches: {len(matches)}")


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN environment variable first.")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()


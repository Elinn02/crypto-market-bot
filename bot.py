"""
bot.py
Main Telegram bot: /start, /top, /coin, /movers, /picks, /picks_early,
/watch, /mywatches, plus background jobs for price alerts (2 min) and
news monitoring for notable-figure mentions (5 min).
"""

import os
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
)

import market_data
import news_monitor
import cmc_data
import keep_alive

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Start the keep-alive port immediately on import, before anything else,
# so Render's port scan detects it right away instead of waiting for the
# bot/token setup to finish.
keep_alive.start()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

# In-memory watch list: {chat_id: [{"coin_id": str, "target_price": float}]}
watchlists = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 ربات تحلیل ارز آماده‌ست.\n\n"
        "/top - کوین‌های برتر با برچسب ریسک\n"
        "/coin <نام> - جزئیات کامل یک کوین\n"
        "/movers - تغییرات غیرعادی ۲۴ ساعته\n"
        "/picks - پیشنهاد ۸ کوین (مارکت‌کپ بالا/متوسط)\n"
        "/picks_early - پیشنهاد ۸ کوین جدید/کوچک (ریسک خیلی بالا)\n"
        "/watch <coin> <price> - هشدار قیمت\n"
        "/mywatches - لیست هشدارهای فعال"
    )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        coins = market_data.get_top_coins(limit=20)
    except Exception as e:
        await update.message.reply_text(f"خطا در دریافت اطلاعات: {e}")
        return

    lines = ["📊 کوین‌های برتر:\n"]
    for c in coins:
        lines.append(
            f"{c['market_cap_rank']}. {c['name']} ({c['symbol']}) — "
            f"${c['price']:.4f} | 24h: {c['change_24h']:.1f}% | {c['risk']}"
        )
    await update.message.reply_text("\n".join(lines))


async def coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استفاده: /coin bitcoin (یا هر coin id از coingecko)")
        return

    coin_id = context.args[0].lower()
    try:
        d = market_data.get_coin_detail(coin_id)
    except Exception as e:
        await update.message.reply_text(f"کوین پیدا نشد یا خطا: {e}")
        return

    lines = [
        f"🪙 {d['name']} ({d['symbol']})",
        f"قیمت: ${d['price']}",
        f"رنک مارکت‌کپ: {d['market_cap_rank']}",
        f"تغییر 24h: {d['change_24h']:.1f}% | 7d: {d['change_7d']:.1f}%" if d['change_24h'] is not None else "",
        f"RSI (7d): {d['rsi']}" if d['rsi'] else "RSI: داده کافی نیست",
        f"سن کوین: {d['age_days']} روز" if d['age_days'] is not None else "",
        f"رضایت کامیونیتی: {d['sentiment_up_pct']}%" if d['sentiment_up_pct'] is not None else "",
        f"ریسک: {d['risk']}",
    ]

    if d["scam_flags"]:
        lines.append("\n⚠️ پرچم‌های هشدار:")
        lines.extend(f"- {flag}" for flag in d["scam_flags"])

    if d["explorer_links"]:
        lines.append("\n🔍 لینک وریفای قرارداد:")
        lines.extend(d["explorer_links"])

    cross = cmc_data.cross_check(d["symbol"], d["price"])
    if cross and cross["warning"]:
        lines.append(f"\n{cross['warning']} (CMC: ${cross['cmc_price']})")

    await update.message.reply_text("\n".join(filter(None, lines)))


async def movers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        m = market_data.get_movers()
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
        return

    if not m:
        await update.message.reply_text("در حال حاضر تغییر غیرعادی‌ای دیده نشد.")
        return

    lines = ["🚨 تغییرات غیرعادی ۲۴ ساعته:\n"]
    for c in m:
        lines.append(f"{c['name']} ({c['symbol']}): {c['change_24h']:.1f}% | {c['risk']}")
    await update.message.reply_text("\n".join(lines))


async def picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        p = market_data.get_picks(early=False)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
        return

    if not p:
        await update.message.reply_text("در حال حاضر پیشنهادی که شرایط رو داشته باشه پیدا نشد.")
        return

    lines = ["✅ پیشنهادهای امروز (مارکت‌کپ بالا/متوسط):\n"]
    for c in p:
        lines.append(f"{c['name']} ({c['symbol']}) — امتیاز: {c['score']} | {c['risk']}")
    await update.message.reply_text("\n".join(lines))


async def picks_early(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        p = market_data.get_picks(early=True)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
        return

    if not p:
        await update.message.reply_text("در حال حاضر پیشنهاد جدید/کوچکی پیدا نشد.")
        return

    lines = ["🔥 پیشنهادهای کوین‌های جدید/کوچک (ریسک خیلی بالا):\n"]
    for c in p:
        lines.append(f"{c['name']} ({c['symbol']}) — امتیاز: {c['score']} | {c['risk']}")
    await update.message.reply_text("\n".join(lines))


async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /watch bitcoin 65000")
        return

    coin_id = context.args[0].lower()
    try:
        target_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("قیمت باید عدد باشه.")
        return

    chat_id = update.effective_chat.id
    watchlists.setdefault(chat_id, []).append({"coin_id": coin_id, "target_price": target_price})
    await update.message.reply_text(f"✅ هشدار ثبت شد: {coin_id} به قیمت ${target_price}")


async def mywatches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    items = watchlists.get(chat_id, [])
    if not items:
        await update.message.reply_text("هیچ هشداری ثبت نشده.")
        return
    lines = ["👀 هشدارهای فعال شما:\n"]
    for w in items:
        lines.append(f"- {w['coin_id']}: ${w['target_price']}")
    await update.message.reply_text("\n".join(lines))


async def check_price_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Background job every 2 minutes: check watchlists against live prices."""
    for chat_id, items in list(watchlists.items()):
        remaining = []
        for w in items:
            try:
                detail = market_data.get_coin_detail(w["coin_id"])
                price = detail["price"]
            except Exception:
                remaining.append(w)
                continue

            if price is not None and price >= w["target_price"]:
                await context.bot.send_message(
                    chat_id,
                    f"🔔 {w['coin_id']} به قیمت ${price} رسید (هدف: ${w['target_price']})",
                )
            else:
                remaining.append(w)
        watchlists[chat_id] = remaining


async def check_news(context: ContextTypes.DEFAULT_TYPE):
    """Background job every 5 minutes: scan RSS for notable-figure mentions."""
    try:
        alerts = news_monitor.check_for_mentions()
    except Exception as e:
        logger.warning(f"news check failed: {e}")
        return

    if not alerts:
        return

    for chat_id in watchlists.keys():
        for a in alerts:
            await context.bot.send_message(
                chat_id,
                f"📰 {a['figure']} در خبرها: {a['title']}\n{a['link']}",
            )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN env var is not set")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("coin", coin))
    app.add_handler(CommandHandler("movers", movers))
    app.add_handler(CommandHandler("picks", picks))
    app.add_handler(CommandHandler("picks_early", picks_early))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("mywatches", mywatches))

    job_queue = app.job_queue
    job_queue.run_repeating(check_price_alerts, interval=120, first=30)
    job_queue.run_repeating(check_news, interval=300, first=60)

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()

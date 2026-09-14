# ربات تحلیل ارز (Telegram Crypto Analysis Bot)

## فایل‌ها
- `bot.py` — بات اصلی تلگرام و همه‌ی دستورات
- `market_data.py` — اتصال به CoinGecko (رایگان)، محاسبه RSI، امتیازدهی /picks
- `cmc_data.py` — کراس‌چک اختیاری با CoinMarketCap
- `news_monitor.py` — چک RSS برای اسم افراد تأثیرگذار
- `requirements.txt` — پکیج‌های لازم
- `.gitignore`

## متغیرهای محیطی لازم (روی Render تنظیم می‌شن)
- `TELEGRAM_BOT_TOKEN` — از BotFather
- `CMC_API_KEY` — اختیاری، بدونش هم بات کار می‌کنه

## اجرا (بعد از دیپلوی)
Render این دستور رو اجرا می‌کنه: `python bot.py`

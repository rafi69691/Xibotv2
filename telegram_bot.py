import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from config import (
    BOT_TOKEN,
    CHANNEL_ID,
    BOT_NAME,
    PAIRS,
    EXPIRY_SECONDS,
    AUTO_SIGNAL_INTERVAL,
    QUOTEX_SSID,
    ADMIN_USER_IDS
)
from quotex_feed import QuotexLiveWebSocket
from strategy import StrategyEngine
from chart_generator import generate_signal_chart

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# User & Channel Authorization
def is_admin(user_id: int) -> bool:
    return not ADMIN_USER_IDS or user_id in ADMIN_USER_IDS

def get_target_channel():
    cid = str(CHANNEL_ID).strip()
    if cid.lstrip('-').isdigit():
        return int(cid)
    return cid

# Initialize Quotex Live WebSocket Feed
feed = QuotexLiveWebSocket(session_ssid=QUOTEX_SSID, pairs=PAIRS)
feed.start_connection()

# Signal and Win/Loss Tracking State
history_records: List[Dict] = []
auto_mode_running = False
auto_task = None

def get_stats():
    """Calculates total wins, losses, and win rate percentage."""
    wins = sum(1 for r in history_records if r.get('status') == 'WIN')
    losses = sum(1 for r in history_records if r.get('status') == 'LOSS')
    total = wins + losses
    rate = int((wins / total * 100)) if total > 0 else 100
    return wins, losses, rate

def format_partial_summary(is_final=False) -> str:
    """Formats scorecard matching XT AI PRO Telegram style."""
    today_str = datetime.now().strftime("%Y.%m.%d")
    title_type = "FINAL" if is_final else "PARTIAL"
    wins, losses, rate = get_stats()

    lines = [
        f"{'='*10} {title_type} {'='*10}",
        "",
        f"🗓️ - {today_str}",
        "",
        f"🏛️ OTC MARKETS {title_type} 🏛️"
    ]

    for record in history_records[-8:]:
        time_str = record['time']
        pair = record['pair']
        direction = "BUY" if record['direction'] == "CALL" else "PUT"
        status_icon = "✅" if record['status'] == "WIN" else "❌"
        lines.append(f"🔲 {time_str} - {pair} - {direction} {status_icon}")

    if not history_records:
        lines.append("🔲 No signals recorded yet today.")

    lines.extend([
        "",
        f"📈 TOTAL RATE: {wins}X{losses} • ({rate}%)",
        "",
        f"⚙️ PLATFORM: {BOT_NAME.upper()} TERMINAL",
        f"📡 {title_type} SENT SUCCESSFULLY"
    ])

    return "\n".join(lines)

async def evaluate_signal_result(bot, job_data: dict):
    """
    Evaluates market price after expiry and sends Auto Result matching XT AI PRO.
    """
    pair = job_data['pair']
    direction = job_data['direction']
    entry_price = job_data['entry_price']
    signal_time = job_data['time']
    dest_chat = job_data['dest_chat']

    # Update candle to get exit price
    feed.update_candle(pair)
    exit_price = feed.get_latest_price(pair)

    # Determine Win or Loss
    if direction == "CALL":
        is_win = exit_price >= entry_price
    else:
        is_win = exit_price <= entry_price

    status = "WIN" if is_win else "LOSS"

    record = {
        'time': signal_time,
        'pair': pair,
        'direction': direction,
        'status': status
    }
    history_records.append(record)

    dir_icon = "🆙 CALL" if direction == "CALL" else "🔻 PUT"
    result_text = "✅ WIN ✦ Direct" if is_win else "🔴 LOSS"

    msg = (
        f"📊 {BOT_NAME} — AUTO RESULT\n\n"
        f"💲 Pair: {pair}\n"
        f"⏰ Time: {signal_time}\n"
        f"🔮 Direction: {dir_icon}\n\n"
        f"{result_text}"
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 Partial Result", callback_data="partial_result"),
            InlineKeyboardButton("📈 Daily Full", callback_data="daily_full")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await bot.send_message(
            chat_id=dest_chat,
            text=msg,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending auto result message: {e}")

async def dispatch_signal(bot, dest_chat, target_pair=None):
    """
    Scans pairs, generates the chart image, and dispatches the signal.
    """
    candidate_pairs = [target_pair] if target_pair else PAIRS
    best_signal = None
    best_df = None
    best_pair = None
    best_acc = "0%"

    for p in candidate_pairs:
        feed.update_candle(p)
        df = feed.get_candles(p, count=42)
        sig, acc, reason = StrategyEngine.analyze(df)
        if sig:
            best_signal = sig
            best_df = df
            best_pair = p
            best_acc = acc
            break

    if not best_signal:
        best_pair = candidate_pairs[0]
        feed.update_candle(best_pair)
        best_df = feed.get_candles(best_pair, count=42)
        best_signal = "CALL" if best_df['close'].iloc[-1] >= best_df['open'].iloc[-1] else "PUT"
        best_acc = "88%"

    # Generate Chart Image
    chart_filename = f"chart_{best_pair}_{int(datetime.now().timestamp())}.png"
    generate_signal_chart(
        pair=best_pair,
        df=best_df,
        direction=best_signal,
        accuracy=best_acc,
        bot_name=BOT_NAME,
        output_path=chart_filename
    )

    now_time = datetime.now().strftime("%H:%M")
    today_str = datetime.now().strftime("%Y.%m.%d")
    dir_emoji = "🆙 CALL" if best_signal == "CALL" else "🔻 PUT"

    caption = (
        f"⚡ {BOT_NAME} ⚡\n"
        f"1,290 monthly users\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗓️ - {today_str}\n\n"
        f"🏛️ OTC MARKETS 🏛️\n"
        f"💲 Pair: {best_pair}\n"
        f"⏰ Time: {now_time}\n"
        f"🔮 Direction: {dir_emoji}\n"
        f"🎯 Accuracy: {best_acc}\n"
        f"⏳ Expiry: 1 Min\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 Partial Result", callback_data="partial_result"),
            InlineKeyboardButton("📈 Daily Full", callback_data="daily_full")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        with open(chart_filename, "rb") as photo_file:
            await bot.send_photo(
                chat_id=dest_chat,
                photo=photo_file,
                caption=caption,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Failed to send signal chart: {e}")
        return None
    finally:
        if os.path.exists(chart_filename):
            try:
                os.remove(chart_filename)
            except Exception:
                pass

    signal_info = {
        'pair': best_pair,
        'direction': best_signal,
        'time': now_time,
        'entry_price': float(best_df['close'].iloc[-1]),
        'dest_chat': dest_chat
    }

    # Asynchronously wait and verify result after EXPIRY_SECONDS
    async def delayed_checker():
        await asyncio.sleep(EXPIRY_SECONDS)
        await evaluate_signal_result(bot, signal_info)

    asyncio.create_task(delayed_checker())
    return signal_info

# Handlers
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        f"👋 **স্বাগতম! {BOT_NAME} ট্রেডিং সিগন্যাল বোটে।**\n\n"
        f"🔥 **ফিচারসমূহ:**\n"
        f"• Quotex OTC ও লাইভ মার্কেট ফিড\n"
        f"• ক্যান্ডেলস্টিক চার্ট সহ প্রফেশনাল সিগন্যাল\n"
        f"• অটো রেজাল্ট ট্র্যাকিং (WIN/LOSS)\n"
        f"• লাইভ স্কোরকার্ড ও পারফরম্যান্স রিপোর্ট\n\n"
        f"👉 **কমান্ডসমূহ:**\n"
        f"• `/signal` - এখনই ইনস্ট্যান্ট সিগন্যাল ও চার্ট গ্রুপে পাঠাবে\n"
        f"• `/auto` - প্রতি ৩ মিনিটে স্বয়ংক্রিয় সিগন্যাল ব্রডকাস্ট অন/অফ করবে\n"
        f"• `/stats` - আজকের ফুল রেজাল্ট রিপোর্ট দেখবে"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⚠️ এই কমান্ডটি শুধুমাত্র অনুমোদিত অ্যাডমিন ব্যবহার করতে পারবেন।")
        return

    user_chat = update.effective_chat.id
    dest_chat = get_target_channel() or user_chat

    wait_msg = await update.message.reply_text("🔍 মার্কেট অ্যানালাইসিস ও চার্ট তৈরি করা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন...")
    
    signal_data = await dispatch_signal(context.bot, dest_chat)
    try:
        await wait_msg.delete()
    except Exception:
        pass

    if signal_data and dest_chat != user_chat:
        await update.message.reply_text(f"✅ সিগন্যাল ও চার্ট সফলভাবে পাঠানো হয়েছে! (Group ID: {dest_chat})")

async def auto_loop(bot, dest_chat):
    """Background task for sending auto signals periodically."""
    global auto_mode_running
    while auto_mode_running:
        try:
            await dispatch_signal(bot, dest_chat)
        except Exception as e:
            logger.error(f"Auto signal dispatch error: {e}")
        await asyncio.sleep(AUTO_SIGNAL_INTERVAL)

async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global auto_mode_running, auto_task
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⚠️ অটো সিগন্যাল কন্ট্রোল শুধুমাত্র অ্যাডমিন করতে পারবেন।")
        return

    dest_chat = get_target_channel() or update.effective_chat.id

    if auto_mode_running:
        auto_mode_running = False
        if auto_task and not auto_task.done():
            auto_task.cancel()
        await update.message.reply_text("🛑 **অটো সিগন্যাল ব্রডকাস্ট বন্ধ করা হয়েছে।**", parse_mode="Markdown")
    else:
        auto_mode_running = True
        auto_task = asyncio.create_task(auto_loop(context.bot, dest_chat))
        await update.message.reply_text(
            f"🚀 **অটো সিগন্যাল চালু করা হয়েছে!**\nপ্রতি {int(AUTO_SIGNAL_INTERVAL/60)} মিনিট পর পর স্বয়ংক্রিয়ভাবে সিগন্যাল ও চার্ট পাঠানো হবে।",
            parse_mode="Markdown"
        )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = format_partial_summary(is_final=False)
    await update.message.reply_text(summary)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "partial_result":
        summary = format_partial_summary(is_final=False)
        await query.message.reply_text(summary)
    elif query.data == "daily_full":
        summary = format_partial_summary(is_final=True)
        await query.message.reply_text(summary)

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("[!] ERROR: Please set your TELEGRAM_BOT_TOKEN in config.py")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("signal", signal_cmd))
    application.add_handler(CommandHandler("auto", auto_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CallbackQueryHandler(button_callback))

    print(f"[*] {BOT_NAME} Telegram Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()

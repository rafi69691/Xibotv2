import os

# Telegram Bot Credentials
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8141840805:AAG26S7PtJPu-eNOVJRPsDuIizAM2wRySQs")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "-1004314091975")

# Admin Telegram User IDs (Only these IDs can control /auto and /signal)
ADMIN_USER_IDS = [7215230722]

# Quotex Real WebSocket Session
# Automatically stripped of any mobile copy-paste spaces
RAW_SSID = """eyJpdil6lkdZV21Jd0tvRy9nRGY2YXlwMHhwV3c9PSIsInZhbHVlljoid 1dHM2VETVhaek44UjV5cnF1OEpYVmlTUIhRUk9HTU12M0sxU1Yze jZCSXIKNHdrY0Vwck1JSVFJMnpNZIpQbmtCdktWTDFic1J5QTY5T mVjRFRLQ3JOaTNmUUcwSTVXaEs5L0ZIcjk3d29vZzlYMjV2TXB3Q XRBd1JJNFB3QysiLCJtYWMiOil5Y2I3NTI1YzM4ZilkNGM2N2NhYW JIMWMxNmQzN2YwNzc4ZjExN2M4ZmE2MGM1MjVIOTAwMWJIM DZiNDUyNGVkliwidGFnljoiln0%3D"""
QUOTEX_SSID = "".join(RAW_SSID.split())

# Quotex Mirror Domain
QUOTEX_DOMAIN = "market-qx.info"

# Bot Branding & Settings
BOT_NAME = "XT AI PRO V5"

# Supported Quotex OTC & Forex Pairs
PAIRS = [
    "USDMXN-OTC",
    "AUDCAD-OTC",
    "XRPUSD-OTC",
    "EURUSD-OTC",
    "GBPUSD-OTC",
    "USDJPY-OTC",
    "NZDUSD-OTC",
    "BTCUSD-OTC"
]

# Signal Frequency & Expiry Settings
TIMEFRAME = "1M"           # 1 Minute candles
EXPIRY_SECONDS = 60        # 60s for 1M binary expiry
AUTO_SIGNAL_INTERVAL = 180 # Check for new signal every 3 minutes (in seconds)
MIN_ACCURACY_THRESHOLD = 82 # Only send signals with >= 82% confidence

import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException
from typing import Optional

app = FastAPI(
    title="Groww Options Live API",
    version="1.0.0"
)

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "x-app-id": "growwWeb",
    "user-agent": "Mozilla/5.0"
}

TIMEOUT = aiohttp.ClientTimeout(total=8)
MAX_RETRIES = 3


# =====================================================
# 🔐 SAFE ASYNC GROWW LIVE FETCH
# =====================================================
async def fetch_day_high_low_async(
    option_id: str,
    session: aiohttp.ClientSession
):
    if not option_id:
        return None, None, None, None, False

    option_id = option_id.upper()

    # -----------------------------
    # SYMBOL → EXCHANGE MAPPING
    # -----------------------------
    if option_id.startswith("SENSEX"):
        exchange = "BSE"
        api_type = "tr_live_book"
    else:
        exchange = "NSE"
        api_type = "tr_live_prices"

    # -----------------------------
    # BUILD GROWW URL
    # -----------------------------
    url = (
        f"https://groww.in/v1/api/stocks_fo_data/v1/"
        f"{api_type}/exchange/{exchange}/segment/FNO/"
        f"{option_id}/latest"
    )

    # -----------------------------
    # RETRY LOOP
    # -----------------------------
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status
                    )

                j = await resp.json()

                return (
                    j.get("high"),
                    j.get("low"),
                    j.get("open"),
                    j.get("close"),
                    True
                )

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError
        ):
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)

    return None, None, None, None, False


# =====================================================
# 🌐 API ROUTE
# =====================================================
@app.get("/option/live/{option_id}")
async def get_option_live(option_id: str):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        high, low, open_, close, market_open = await fetch_day_high_low_async(
            option_id,
            session
        )

        if high is None and low is None:
            raise HTTPException(
                status_code=503,
                detail="Failed to fetch live data"
            )

        return {
            "option_id": option_id.upper(),
            "day_high": high,
            "day_low": low,
            "open": open_,
            "close": close,
            "market_open": market_open
        }


# =====================================================
# HEALTH CHECK
# =====================================================
@app.get("/")
def health():
    return {"status": "ok"}

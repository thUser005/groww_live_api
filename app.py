import asyncio
import aiohttp
from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Groww Options Live API",
    version="1.0.0"
)

# =====================================================
# CONFIG
# =====================================================
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "x-app-id": "growwWeb",
    "user-agent": "Mozilla/5.0"
}

TIMEOUT = aiohttp.ClientTimeout(total=8)
MAX_RETRIES = 3

# =====================================================
# 🔐 SAFE ASYNC GROWW LIVE FETCH (UNCHANGED LOGIC)
# =====================================================
async def fetch_day_high_low_async(
    option_id: str,
    session: aiohttp.ClientSession
):
    if not option_id:
        return None

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
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status
                    )

                obj_data = await resp.json()
                return obj_data if obj_data else None

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError
        ):
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(0.5)

    return None


# =====================================================
# 🔁 GLOBAL SESSION (IMPORTANT FOR 600 CALLS)
# =====================================================
@app.on_event("startup")
async def startup_event():
    connector = aiohttp.TCPConnector(
        limit=200,              # max concurrent connections
        limit_per_host=200,
        ttl_dns_cache=300
    )

    app.state.session = aiohttp.ClientSession(
        headers=HEADERS,
        timeout=TIMEOUT,
        connector=connector
    )


@app.on_event("shutdown")
async def shutdown_event():
    await app.state.session.close()


# =====================================================
# 🌐 API ROUTE (THREAD-SAFE & FAST)
# =====================================================
@app.get("/option/live/{option_id}")
async def get_option_live(option_id: str):
    session = app.state.session

    obj_data = await fetch_day_high_low_async(
        option_id,
        session
    )

    if obj_data is None:
        raise HTTPException(
            status_code=503,
            detail="Failed to fetch live data"
        )

    obj_data["option_id"] = option_id.upper()
    return obj_data


# =====================================================
# HEALTH CHECK
# =====================================================
@app.get("/")
def health():
    return {"status": "ok"}

import asyncio
import aiohttp, json
from fastapi import FastAPI, HTTPException
import subprocess
import shutil
import re
import os
import threading
import uvicorn
import time
import sys

# =====================================================
# 🔧 CONFIG FLAG (CLI BASED)
# =====================================================
cloud_mode = False  # default

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cloud_mode = sys.argv[1].lower() == "true"

LOCAL_PORT = int(os.getenv("PORT", 8000))
CLOUDFLARE_ENV_FILE = "keys_data.json"

# =====================================================
# FASTAPI APP
# =====================================================
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
# 🔐 SAFE ASYNC GROWW LIVE FETCH (UNCHANGED)
# =====================================================
async def fetch_day_high_low_async(option_id: str, session: aiohttp.ClientSession):
    if not option_id:
        return None

    option_id = option_id.upper()

    if option_id.startswith("SENSEX"):
        exchange = "BSE"
        api_type = "tr_live_book"
    else:
        exchange = "NSE"
        api_type = "tr_live_prices"

    url = (
        f"https://groww.in/v1/api/stocks_fo_data/v1/"
        f"{api_type}/exchange/{exchange}/segment/FNO/"
        f"{option_id}/latest"
    )

    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(url, timeout=TIMEOUT) as resp:
                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        resp.request_info, resp.history, status=resp.status
                    )
                data = await resp.json()
                return data if isinstance(data, dict) else None

        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)

    return None


# =====================================================
# 🌐 API ROUTE (UNCHANGED)
# =====================================================
@app.get("/option/live/{option_id}")
async def get_option_live(option_id: str):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        data = await fetch_day_high_low_async(option_id, session)

        if data is None:
            raise HTTPException(status_code=503, detail="Failed to fetch live data")

        data["option_id"] = option_id.upper()
        return data


# =====================================================
# ❤️ HEALTH CHECK (UNCHANGED)
# =====================================================
@app.get("/")
def health():
    return {"status": "ok"}


# =====================================================
# ☁️ CLOUDFLARE HELPERS
# =====================================================
def install_cloudflared():
    if shutil.which("cloudflared"):
        return

    subprocess.run([
        "curl", "-fsSL",
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        "-o", "cloudflared"
    ], check=True)
    subprocess.run(["chmod", "+x", "cloudflared"], check=True)


# =====================================================
# ☁️ CLOUDFLARE TUNNEL (REFERENCE VERSION – WORKING)
# =====================================================
def start_cloudflare_tunnel(port):
    proc = subprocess.Popen(
        ["./cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    public_url = None
    for line in iter(proc.stdout.readline, ""):
        print("[Cloudflare]", line.strip())
        if "trycloudflare.com" in line:
            match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if match:
                public_url = match.group(0)
                print("🌍 Public URL:", public_url)

                with open(CLOUDFLARE_ENV_FILE, "w", encoding="utf-8") as f:
                    json.dump({"public_name": public_url}, f, indent=4)
                break

    return proc, public_url


# =====================================================
# 🚀 STARTERS (UNCHANGED)
# =====================================================
def start_api():
    uvicorn.run(app, host="0.0.0.0", port=LOCAL_PORT, log_level="error")


if __name__ == "__main__":
    if cloud_mode:
        print("☁️ Cloud mode ENABLED (Colab / Tunnel)")

        install_cloudflared()

        # 🔹 Start API in background
        threading.Thread(target=start_api, daemon=True).start()

        # 🔹 Start tunnel (blocking UNTIL URL appears)
        _, public_url = start_cloudflare_tunnel(LOCAL_PORT)

        print("🚀 API + Cloudflare running")
        print("💡 Public URL saved to keys_data.json")

    else:
        print("🖥️ Normal mode (Railway / VS Code)")
        start_api()

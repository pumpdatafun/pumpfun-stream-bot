"""A pump.fun bot on pumpdata.fun: find, watch on the stream, buy, exit. Paper mode unless LIVE=1.

  pip install requests websockets solders
  PUMPDATA_KEY=pdk_... python bot.py                       # paper: prints what it would do
  PUMPDATA_KEY=pdk_... WALLET_SECRET=... LIVE=1 python bot.py

The rules below are examples, not advice. Most pump.fun coins go to zero.
Guide: https://pumpdata.fun/pump-fun-trading-bot-guide
"""
import asyncio, base64, json, os, time
import requests, websockets

API = "https://pumpdata.fun"
KEY = os.environ["PUMPDATA_KEY"]
H = {"x-api-key": KEY}
LIVE = os.environ.get("LIVE") == "1"
SIZE_SOL = 0.05      # SOL per buy
MAX_FOLLOW = 20      # coins watched or held at once (the bot plan follows 20, the whole stream 200)
MIN_BUYERS = 8       # different buyers in a minute before buying
TAKE, STOP = 1.5, 0.7  # sell at 1.5x or 0.7x the market cap at entry

watching, holding = {}, {}   # mint -> state
changed = asyncio.Event()    # the followed coins changed: reconnect the stream


def get(path):
    r = requests.get(API + path, headers=H, timeout=10)
    return r.json() if r.ok else None


def post(path, body):
    r = requests.post(API + path, json=body, headers=H, timeout=30)
    return r.status_code, r.json()


def trade(side, mint):
    """Build with /buy or /sell, sign here, send with /send. The key never leaves this machine."""
    if not LIVE:
        print("paper", side, mint)
        return True
    from solders.keypair import Keypair
    from solders.transaction import VersionedTransaction
    kp = Keypair.from_base58_string(os.environ["WALLET_SECRET"])
    body = {"mint": mint, "wallet": str(kp.pubkey())}
    body.update({"sol": SIZE_SOL} if side == "buy" else {"tokens": "all"})
    code, built = post("/" + side, body)
    if code != 200:
        print(side, "not built:", built)
        return False
    tx = VersionedTransaction.from_bytes(base64.b64decode(built["tx"]))
    signed = VersionedTransaction(tx.message, [kp])
    code, sent = post("/send", {"tx": base64.b64encode(bytes(signed)).decode()})
    # 409 "already sent": this build went out before. Look the signature up; never send it twice.
    print(side, mint, code, sent.get("signature"), sent.get("fills"))
    return code == 200


async def find():
    """Step 1: candidates. Here, the coins that pass the screener; any feed works."""
    while True:
        screen = await asyncio.to_thread(get, "/screener.json") or {}
        for row in screen.get("pass", []):
            m = row["mint"]
            if m not in watching and m not in holding and len(watching) + len(holding) < MAX_FOLLOW:
                watching[m] = {"since": time.time(), "buys": [], "wallets": set(), "same": set()}
                changed.set()
        await asyncio.sleep(60)


async def leave(mint, why):
    if holding.pop(mint, None) is not None:
        print("exit", mint, why)
        await asyncio.to_thread(trade, "sell", mint)
        changed.set()


async def on_trade(ev):
    """Steps 3 and 5: every trade on a followed coin arrives here about 1.5 s after its block."""
    m = ev.get("mint")
    if ev.get("type") != "trade":
        return
    if ev["side"] == "sell" and ev.get("top_holder_sell"):
        if m in holding:
            await leave(m, "a top holder sold")
        elif watching.pop(m, None) is not None:
            print("skip", m, "a top holder sold before we bought")
            changed.set()
    elif ev["side"] == "buy" and m in watching:
        w = watching[m]
        # wallets buying a near-identical amount in the same slot count as one buyer
        same = (ev["slot"], round(ev.get("sol") or 0, 2))
        if ev["wallet"] not in w["wallets"] and same not in w["same"]:
            w["buys"].append(time.time())
        w["wallets"].add(ev["wallet"])
        w["same"].add(same)


async def listen():
    while True:
        mints = ",".join([*watching, *holding])
        if not mints:
            await asyncio.sleep(5)
            continue
        changed.clear()
        url = f"wss://pumpdata.fun/stream?key={KEY}&types=trade&mints={mints}"
        try:
            async with websockets.connect(url) as ws:
                while not changed.is_set():
                    try:
                        await on_trade(json.loads(await asyncio.wait_for(ws.recv(), 5)))
                    except asyncio.TimeoutError:
                        pass
        except Exception as e:   # closed, refused, or too slow to keep up: connect again
            print("stream:", e)
            await asyncio.sleep(2)


async def manage():
    """Steps 2, 4 and 5: decide on the coins watched, and take or stop on the coins held."""
    while True:
        now = time.time()
        for m, w in list(watching.items()):
            if now - w["since"] < 60:
                continue
            buyers = sum(1 for t in w["buys"] if now - t < 60)
            if buyers >= MIN_BUYERS:
                coin = await asyncio.to_thread(get, f"/now/{m}.json") or {}
                del watching[m]
                if coin.get("market_cap_usd") and await asyncio.to_thread(trade, "buy", m):
                    holding[m] = {"entry": coin["market_cap_usd"]}
                changed.set()
            elif now - w["since"] > 900:
                del watching[m]
                changed.set()
        for m, h in list(holding.items()):
            coin = await asyncio.to_thread(get, f"/now/{m}.json") or {}
            cap = coin.get("market_cap_usd")
            if cap and (cap >= h["entry"] * TAKE or cap <= h["entry"] * STOP):
                await leave(m, "take" if cap >= h["entry"] else "stop")
        await asyncio.sleep(10)


async def main():
    await asyncio.gather(find(), listen(), manage())

if __name__ == "__main__":
    asyncio.run(main())

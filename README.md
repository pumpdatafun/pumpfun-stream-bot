# pump.fun stream bot

One Python file that runs the loop a pump.fun trading bot needs, on [pumpdata.fun](https://pumpdata.fun):

1. **Find** coins from a free feed (here, the screener's passes).
2. **Watch** them on the WebSocket stream: every buy and sell, about 1.5 seconds after its block.
3. **Buy** when enough different wallets are buying.
4. **Exit** when a top holder sells, or at a take or stop.

It trades on paper until you set `LIVE=1`.

The full guide, step by step: **[pumpdata.fun/pump-fun-trading-bot-guide](https://pumpdata.fun/pump-fun-trading-bot-guide)**

## Run it

```bash
pip install -r requirements.txt
PUMPDATA_KEY=pdk_... python bot.py
```

Get a free key at [pumpdata.fun/keys](https://pumpdata.fun/keys). The stream has a 30-day free trial that starts the first time your key connects.

In paper mode the bot prints what it would do:

```
paper buy 7xKp...pump
skip 9mQd...pump a top holder sold before we bought
exit 7xKp...pump a top holder sold
paper sell 7xKp...pump
```

## Go live

```bash
PUMPDATA_KEY=pdk_... WALLET_SECRET=<base58 secret key> LIVE=1 python bot.py
```

pumpdata builds each trade and the bot signs it on your machine. Your key is never sent anywhere. The fee is 0.4% of the SOL side of each trade.

Use a wallet that holds only what you are ready to lose.

## Change the rules

The numbers at the top of `bot.py` are placeholders:

| Setting | Default | What it does |
|---|---|---|
| `SIZE_SOL` | 0.05 | SOL per buy |
| `MAX_FOLLOW` | 20 | coins watched or held at once |
| `MIN_BUYERS` | 8 | different buyers in a minute before buying |
| `TAKE`, `STOP` | 1.5, 0.7 | sell at this multiple of the market cap at entry |

Run it on paper, log what it would have done, and change them from what you see. To test a rule over months of past launches, use the [bulk files](https://pumpdata.fun/pump-fun-bulk-data).

## What the stream sends

Each trade on a coin you follow is one JSON message:

```json
{"type":"trade","venue":"pumpswap","slot":466369940,"ts":1794023998,"mint":"C5xph2...pump","wallet":"7jQwHd...hch","side":"sell","sol":8.4,"seller_rank":3,"seller_share_pct":11.8,"sold_pct":34.2,"top_holder_sell":true}
```

`top_holder_sell` is true when a top-10 holder with at least 1% of the supply sells 25% or more of its holding. Every field: [pumpdata.fun/pump-fun-stream](https://pumpdata.fun/pump-fun-stream).

## Notes

- The stream is about 1.5 seconds behind the chain. This bot does not win the first block of a launch.
- Nothing here is advice. Most pump.fun coins go to zero.
- Not affiliated with pump.fun.

Questions or something missing: support@pumpdata.fun. MIT licence.

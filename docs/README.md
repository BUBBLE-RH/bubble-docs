# $BUBBLE

**The AI trade, on-chain.** Priced directly in $NVDA on Robinhood Chain. Every trade buys it back. Every round pays holders.

> Not affiliated with, endorsed by, or connected to NVIDIA Corporation, Robinhood Markets, or Pons Labs. $BUBBLE is a meme token. It can go to zero.

---

## The idea

The AI boom made VCs, engineers, and Wall Street rich. "Up only" used to be for crypto, now it's AI.  

But on a fundamental level, how has this bubble stayed inflated? It's pretty simple - same money, circling between the same five companies, counted as revenue every time it changes hands. Although there's no denying its use-case, the AI boom has been inflated by the same money rotated between the same companies. The worst part - crypto has been sidelined by this shiny new tech. Not anymore -  We put the loop on-chain to reclaim our rightful ownership of the "Bubble". 

$BUBBLE is priced in $NVDA — the chip the whole sector runs on. Fees arrive in NVDA. A share buys $BUBBLE back off the market. A share goes back to the people holding it. The chip pays the bubble; the bubble pays you - Repeat. 

Will it pop? Ask $NVDA.

---

## The loop

This isn't a story. It's supply and demand with one requirement: money keeps changing hands.

Every trade pays a fee in NVDA. Part of that fee buys $BUBBLE off the market and locks it — supply down. Part of it comes back to holders as $BUBBLE — which they hold, or sell, or use to buy more. Either way it's another trade, and another trade is another fee, and another fee is another buyback.

You buy the bubble. The bubble pays you. You buy more bubble. Repeat.

That's the whole mechanism, and it's the same one the AI sector runs on: it doesn't need new money to keep going, it needs the same money to keep moving. The day the money stops moving is the day it pops — for them and for us. Until then, every hand it changes makes the bubble bigger.

---

## Economics

Every trade pays a **1% base fee** plus a **2% management fee** — like every fund that funded the bubble. Both are fixed at launch and cannot be raised.

| Share of base fee | Where it goes |
|---|---|
| 30% | Pons (protocol) |
| Up to 35% | **Buyback.** Buys $BUBBLE off the market and locks it in the Pons buyback vault, vesting over 5 years. Our share is burned as it vests. |
| 35% | **Rounds.** Accumulates in NVDA. Converted to $BUBBLE and paid to holders each time the bubble raises a round. |
| 1% management fee | Team. Disclosed on-chain; readable on the token contract. |

Buybacks are executed by the protocol and skipped only when a buy would move the price more than 3%. Anything skipped lands with the team, who buy back manually in smaller pieces. 

---

## Rounds

The bubble raises a round every time market cap crosses a milestone. At each round, the NVDA accumulated since the last round is converted to $BUBBLE and paid out to holders.

| Round | Market cap |
|---|---|
| Seed | $1M |
| Series A | $10M |
| Series B | $100M |
| Unicorn | $1B |
| IPO | $10B |

**Who gets paid:** every wallet holding $BUBBLE at the round block, weighted by **time-weighted average balance** over the window since the previous round. Hold 1M tokens for the whole window and you get full weight. Buy 1M the day before and you get a day's worth. There is nothing to stake, lock, register, or claim — hold the token, get paid. 

Excluded: the pool, the Pons curve/locker/vault/escrow, the burn address, team wallets, and contract addresses.

Payouts arrive as $BUBBLE, liquid, in your wallet. They are yours.

---

## Contracts & wallets

Verify everything below on [Robinscan](https://robinscan.io). The token address is the only identifier that cannot be copied.

| | Address |
|---|---|
| $BUBBLE token | `[fill after launch]` |
| Bonding curve | `[fill after launch]` |
| Pair asset (NVDA) | `0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC` |
| Creator wallet (fees) | `0xA2fB67138825Dc119573BB345934395382C95831` |
| Round payout wallet | `0xb208A5602a09ebd184627f0F8A03B0025B4003dA` |
| Pons v2 factory | `0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e` |
| Pons buyback vault | `0x42df2a798f82289E177311362e8f5ccC45c1219c` |
| Pons fee escrow | `0xd3AFEB2a57f70eF218Aa82451c51B2fb0416Ac9e` |
| Pons meme hook | `0xE5e702641Ea86F4ae6cC3cDaeD2B886f976Be044` |

---

## Buyback & burn log

Every six months we call `release()` on the buyback vault and burn our share.

| Date | Released (our share) | Burned | Tx |
|---|---|---|---|
| — | — | — | — |

Live vault balance: `totalLocked(BUBBLE)` on the vault contract.

---

## Round log

| Round | Block | NVDA converted | $BUBBLE paid | Wallets | Allocations file | Txs |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

Each round's full allocation list (every wallet, every amount) and every payout transaction hash is published here.

---

## FAQ

**Why NVDA?**
Because it's the most liquid stock token on Robinhood Chain, and because it's the asset the entire AI trade prices itself against. 

**Does NVDA's price move $BUBBLE?**
Yes, by construction. $BUBBLE's dollar price is its NVDA price times NVDA's dollar price. NVDA up, bubble up. NVDA down, bubble down — even if nobody traded.

**What's the snipe tax I saw at launch?**
Pons applies a 99% tax on buys in the first ~5 seconds of a launch, decaying to zero. It stops bots from front-running the open. It only applies to buys, only in the first seconds, and what it collects flows into fees like everything else.

**Why "up to 35%" on buybacks?**
The protocol skips a buyback if it would move the price more than 3%. That money comes to the team instead, and we buy back manually in smaller pieces. Early on, with thin liquidity, expect more of this.

**Why are buybacks locked instead of burned immediately?**
That's how the Pons vault works — bought-back tokens vest over 5 years, split 70/30 between creator and protocol. We burn our 70% as it vests. Pons' 30% is theirs.

**Can the team change the fees?**
No. The base fee, the management fee, the split, and the pair asset are fixed at launch by the Pons contracts. The only thing the team can toggle is buybacks on/off. Liquidity is locked permanently; there is no function to withdraw it.

**Is this financial advice?**
No. It's a meme token about a bubble. Trade what you can afford to lose.

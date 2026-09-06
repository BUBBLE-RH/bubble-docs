"""
$BUBBLE round script -- time-weighted snapshot + batch payout.

Two commands:

  python round.py snapshot --from-block A --to-block B --payout 12345.67
      Pulls every Transfer since launch, replays balances, computes each wallet's
      time-weighted average balance over blocks [A, B], and writes allocations.json
      (address -> BUBBLE amount) for a total payout of --payout BUBBLE tokens.

  python round.py distribute
      Sends the allocations from allocations.json, one ERC-20 transfer per wallet,
      from the airdrop wallet. Resumable: paid addresses are recorded in paid.json
      and skipped on re-run. Runs in DRY_RUN=1 mode unless you set DRY_RUN=0.

Workflow per round:
  1. Claim NVDA from the fee escrow -> send to the airdrop wallet.
  2. Buy $BUBBLE with it in chunks (Pons UI). Note the total BUBBLE you now hold.
  3. Run `snapshot` with the round's block range and that BUBBLE total.
  4. Review allocations.json. Then run `distribute`.
  5. Publish allocations.json + paid.json (tx hashes) on the docs page.

Time weighting uses block numbers as the clock. Robinhood Chain blocks are
fast and regular, so this tracks wall-clock closely; it avoids one RPC call
per block for timestamps.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from decimal import Decimal, getcontext
from pathlib import Path

from web3 import Web3

getcontext().prec = 50

# ----------------------------------------------------------------------------
# CONFIG (env vars; a .env next to this file works with python-dotenv)
# ----------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

RPC_URL = os.environ.get("RH_CHAIN_RPC", "https://rpc.mainnet.chain.robinhood.com")
BUBBLE_TOKEN = os.environ["BUBBLE_TOKEN_ADDR"]          # your token contract
LAUNCH_BLOCK = int(os.environ["LAUNCH_BLOCK"])          # block the TokenLaunched tx landed in
DRY_RUN = os.environ.get("DRY_RUN", "1") == "1"
AIRDROP_PRIVATE_KEY = os.environ.get("AIRDROP_PRIVATE_KEY")   # only needed for `distribute`
LOG_CHUNK = int(os.environ.get("LOG_CHUNK", "5000"))    # blocks per getLogs call; lower if the RPC complains
LOG_DELAY = float(os.environ.get("LOG_DELAY", "0.25"))  # seconds between getLogs calls (public RPC rate limit)

# Addresses that never receive an airdrop. Fill these in after launch.
# Pool liquidity sits inside the Uniswap v4 PoolManager singleton, so it is
# excluded via that address, not via a per-pool address.
EXCLUDED = {a.lower() for a in filter(None, [
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dEaD",
    "0x8366a39cc670b4001a1121b8f6a443a643e40951",   # Uniswap v4 PoolManager
    "0x267444D099b10fB5Ed7c3Cc7B7c767AdcA574952",   # Pons v2 Launch Locker
    "0x42df2a798f82289E177311362e8f5ccC45c1219c",   # Pons v2 Buyback Vault
    "0xd3AFEB2a57f70eF218Aa82451c51B2fb0416Ac9e",   # Pons v2 Fee Escrow
    os.environ.get("CURVE_ADDR", ""),                # your launch's bonding curve
    os.environ.get("CREATOR_WALLET", ""),
    os.environ.get("AIRDROP_WALLET", ""),
    os.environ.get("DEV_BUY_WALLET", ""),            # if different from the above
])}
EXCLUDE_CONTRACTS = os.environ.get("EXCLUDE_CONTRACTS", "1") == "1"   # skip any address with code

ALLOC_FILE = Path("allocations.json")
PAID_FILE = Path("paid.json")
LOGS_CACHE = Path("logs_cache.json")

ERC20_ABI = json.loads("""[
  {"anonymous":false,"name":"Transfer","type":"event","inputs":[
    {"indexed":true,"name":"from","type":"address"},
    {"indexed":true,"name":"to","type":"address"},
    {"indexed":false,"name":"value","type":"uint256"}]},
  {"name":"decimals","type":"function","stateMutability":"view","inputs":[],"outputs":[{"type":"uint8"}]},
  {"name":"balanceOf","type":"function","stateMutability":"view",
   "inputs":[{"name":"a","type":"address"}],"outputs":[{"type":"uint256"}]},
  {"name":"transfer","type":"function","stateMutability":"nonpayable",
   "inputs":[{"name":"to","type":"address"},{"name":"v","type":"uint256"}],"outputs":[{"type":"bool"}]}
]""")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
token = w3.eth.contract(address=Web3.to_checksum_address(BUBBLE_TOKEN), abi=ERC20_ABI)


# ----------------------------------------------------------------------------
# snapshot
# ----------------------------------------------------------------------------
def _slim(log) -> dict:
    return {"b": log["blockNumber"], "i": log["logIndex"],
            "f": log["args"]["from"].lower(), "t": log["args"]["to"].lower(),
            "v": str(log["args"]["value"])}


def fetch_transfers(from_block: int, to_block: int) -> list:
    """All Transfer events in [from_block, to_block]. Cached on disk so a
    re-run only fetches blocks it hasn't seen yet."""
    cache = {"token": BUBBLE_TOKEN.lower(), "cached_to": from_block - 1, "logs": []}
    if LOGS_CACHE.exists():
        c = json.loads(LOGS_CACHE.read_text())
        if c.get("token") == BUBBLE_TOKEN.lower() and c.get("cached_to", -1) >= from_block - 1:
            cache = c
            print(f"  cache: {len(c['logs'])} logs through block {c['cached_to']}", file=sys.stderr)
    out = [l for l in cache["logs"] if l["b"] <= to_block]
    start = max(from_block, cache["cached_to"] + 1)
    chunks_since_save = 0
    while start <= to_block:
        end = min(start + LOG_CHUNK - 1, to_block)
        attempt = 0
        while True:
            try:
                logs = token.events.Transfer.get_logs(from_block=start, to_block=end)
                break
            except Exception as e:
                msg = str(e).lower()
                if any(s in msg for s in ("exceeds limit", "too many", "range too large", "timed out", "timeout")):
                    if end == start:
                        sys.exit(f"single block {start} cannot be served by the RPC")
                    end = start + (end - start) // 2      # too dense or too slow: halve, no wait
                    print(f"  split -> {start}-{end}", file=sys.stderr)
                    continue
                attempt += 1                              # 429 / transient: back off
                if attempt > 8:
                    sys.exit(f"gave up on blocks {start}-{end}")
                wait = min(2 ** attempt, 30)
                print(f"  retry {start}-{end} in {wait}s ({e.__class__.__name__})", file=sys.stderr)
                time.sleep(wait)
        slim = [_slim(l) for l in logs]
        out.extend(slim)
        cache["logs"].extend(slim)
        cache["cached_to"] = end
        chunks_since_save += 1
        if chunks_since_save >= 5:                        # persist regularly; a crash loses at most 5 chunks
            LOGS_CACHE.write_text(json.dumps(cache))
            chunks_since_save = 0
        print(f"  logs {start}-{end}: {len(logs)}", file=sys.stderr)
        start = end + 1
        time.sleep(LOG_DELAY)
    LOGS_CACHE.write_text(json.dumps(cache))
    out.sort(key=lambda l: (l["b"], l["i"]))
    return out


def time_weighted_balances(window_from: int, window_to: int) -> dict:
    """
    Replays every transfer since launch. Accumulates, for each wallet,
    sum(balance * blocks_held) over the window [window_from, window_to].
    Returns {address: weight} where weight is in token-raw-units * blocks.
    """
    logs = fetch_transfers(LAUNCH_BLOCK, window_to)
    balance = defaultdict(int)
    weight = defaultdict(int)
    last_block = defaultdict(lambda: window_from)   # last block a wallet's balance changed (clamped to window)

    def accrue(addr: str, upto: int) -> None:
        """Credit weight for holding `balance[addr]` from last_block[addr] to `upto`."""
        if upto <= window_from:
            return
        lo = max(last_block[addr], window_from)
        if upto > lo and balance[addr] > 0:
            weight[addr] += balance[addr] * (upto - lo)
        last_block[addr] = max(upto, window_from)

    for log in logs:
        blk = log["b"]
        frm = log["f"]
        to = log["t"]
        val = int(log["v"])
        for addr in (frm, to):
            if blk >= window_from:
                accrue(addr, blk)
        balance[frm] -= val
        balance[to] += val
        if blk < window_from:
            last_block[frm] = window_from
            last_block[to] = window_from

    # close out the window for everyone still holding
    for addr in list(balance.keys()):
        accrue(addr, window_to + 1)

    return {a: wt for a, wt in weight.items() if wt > 0}, balance


CODE_CACHE = Path("code_cache.json")
_code_cache = json.loads(CODE_CACHE.read_text()) if CODE_CACHE.exists() else {}

def is_contract(addr: str) -> bool:
    if addr in _code_cache:
        return _code_cache[addr]
    for attempt in range(6):
        try:
            result = len(w3.eth.get_code(Web3.to_checksum_address(addr))) > 0
            break
        except Exception:
            time.sleep(min(2 ** attempt, 20))
    else:
        result = False                      # unreachable after retries: treat as EOA, log it
        print(f"  getCode failed for {addr}; assuming wallet", file=sys.stderr)
    _code_cache[addr] = result
    if len(_code_cache) % 200 == 0:
        CODE_CACHE.write_text(json.dumps(_code_cache))
    time.sleep(LOG_DELAY)
    return result


def cmd_snapshot(args) -> None:
    decimals = token.functions.decimals().call()
    weights, final_balance = time_weighted_balances(args.from_block, args.to_block)

    eligible = {}
    for addr, wt in weights.items():
        if addr in EXCLUDED:
            continue
        if args.require_nonzero and final_balance[addr] <= 0:
            continue
        eligible[addr] = wt

    # Contract check only on wallets whose share would clear --min-raw; the
    # long tail of dust holders never hits the RPC.
    if EXCLUDE_CONTRACTS:
        decimals_ = token.functions.decimals().call()
        payout_raw_ = int(Decimal(args.payout) * (10 ** decimals_))
        total_w_ = sum(eligible.values())
        candidates = [a for a, wt in eligible.items() if payout_raw_ * wt // total_w_ >= args.min_raw]
        print(f"  checking {len(candidates)} wallets for contract code", file=sys.stderr)
        for addr in candidates:
            if is_contract(addr):
                eligible.pop(addr, None)
        CODE_CACHE.write_text(json.dumps(_code_cache))

    total_w = sum(eligible.values())
    if total_w == 0:
        sys.exit("no eligible holders in window")

    payout_raw = int(Decimal(args.payout) * (10 ** decimals))
    allocations = {}
    allocated = 0
    for addr, wt in sorted(eligible.items(), key=lambda kv: -kv[1]):
        amt = payout_raw * wt // total_w
        if amt >= args.min_raw:
            allocations[addr] = amt
            allocated += amt

    report = {
        "token": BUBBLE_TOKEN, "window": [args.from_block, args.to_block],
        "payout_total_raw": payout_raw, "allocated_raw": allocated,
        "dust_unallocated_raw": payout_raw - allocated,
        "holders_eligible": len(eligible), "holders_paid": len(allocations),
        "decimals": decimals, "allocations": allocations,
    }
    ALLOC_FILE.write_text(json.dumps(report, indent=2))
    print(f"wrote {ALLOC_FILE}: {len(allocations)} wallets, "
          f"{Decimal(allocated) / 10 ** decimals} BUBBLE allocated "
          f"({Decimal(payout_raw - allocated) / 10 ** decimals} dust kept)")
    top = sorted(allocations.items(), key=lambda kv: -kv[1])[:10]
    for a, amt in top:
        print(f"  {a}  {Decimal(amt) / 10 ** decimals:,.2f}  ({Decimal(eligible[a]) / total_w:.2%})")


# ----------------------------------------------------------------------------
# distribute
# ----------------------------------------------------------------------------
def cmd_distribute(args) -> None:
    if not AIRDROP_PRIVATE_KEY:
        sys.exit("AIRDROP_PRIVATE_KEY not set")
    acct = w3.eth.account.from_key(AIRDROP_PRIVATE_KEY)
    report = json.loads(ALLOC_FILE.read_text())
    allocations = report["allocations"]
    decimals = report["decimals"]
    paid = json.loads(PAID_FILE.read_text()) if PAID_FILE.exists() else {}

    need = sum(int(v) for a, v in allocations.items() if a not in paid)
    have = token.functions.balanceOf(acct.address).call()
    print(f"airdrop wallet {acct.address}: holds {Decimal(have) / 10 ** decimals:,.2f}, "
          f"needs {Decimal(need) / 10 ** decimals:,.2f} for {sum(1 for a in allocations if a not in paid)} wallets")
    if have < need and not DRY_RUN:
        sys.exit("insufficient BUBBLE in airdrop wallet")

    nonce = w3.eth.get_transaction_count(acct.address)
    chain_id = w3.eth.chain_id
    for addr, amt in allocations.items():
        if addr in paid:
            continue
        if DRY_RUN:
            print(f"[DRY_RUN] {addr} <- {Decimal(amt) / 10 ** decimals:,.4f}")
            nonce += 1
            continue
        tx = token.functions.transfer(Web3.to_checksum_address(addr), int(amt)).build_transaction({
            "from": acct.address, "nonce": nonce, "chainId": chain_id,
        })
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction).hex()
        paid[addr] = {"amount_raw": int(amt), "tx": h}
        PAID_FILE.write_text(json.dumps(paid, indent=2))    # persist after every send
        print(f"{addr} <- {Decimal(amt) / 10 ** decimals:,.4f}  {h}")
        nonce += 1
        time.sleep(args.delay)
    print("done" if not DRY_RUN else "dry run complete -- set DRY_RUN=0 to send")


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot")
    s.add_argument("--from-block", type=int, required=True, help="first block of this round's window (last round's block + 1, or launch block)")
    s.add_argument("--to-block", type=int, required=True, help="block at which the round was hit")
    s.add_argument("--payout", type=str, required=True, help="total BUBBLE to distribute, human units, e.g. 12345.67")
    s.add_argument("--min-raw", type=int, default=0, help="skip allocations below this many raw units")
    s.add_argument("--require-nonzero", action="store_true", default=True, help="only pay wallets still holding at --to-block")
    s.set_defaults(func=cmd_snapshot)

    d = sub.add_parser("distribute")
    d.add_argument("--delay", type=float, default=0.2, help="seconds between sends")
    d.set_defaults(func=cmd_distribute)

    args = p.parse_args()
    args.func(args)

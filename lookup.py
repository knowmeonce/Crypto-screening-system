"""
On-demand coin lookup — run the full pipeline + scoring for one coin
outside the daily schedule, by ticker or contract address.

This is a manual CLI, not a live backend: GitHub Pages only serves
static files, so a genuinely arbitrary "type any address into the
dashboard and get a fresh answer" lookup would need paid serverless
compute, which is outside this project's free-only constraint. The
dashboard's own search box (Phase 4) covers the zero-interaction case
by searching the coins already discovered/tracked that day; this
script is for you to run by hand when you want to check something
that isn't already on the watchlist.

Usage:
    python lookup.py <contract_address> --chain ethereum [--coingecko-id ...]
    python lookup.py <ticker> --chain ethereum --address 0x...
"""

import argparse
import json

import config
from screen import screen_coin
from sources import coingecko


def resolve_and_screen(chain: str, token_address: str, coingecko_id: str | None) -> dict:
    if not coingecko_id:
        platform = config.COINGECKO_PLATFORM_IDS.get(chain)
        if platform:
            try:
                coingecko_id = coingecko.get_coin_id_by_contract(platform, token_address)
            except Exception:
                coingecko_id = None
    return screen_coin(chain, token_address, coingecko_id, defillama_slug=None, record_history=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="On-demand screen for one coin, outside the daily cycle.")
    parser.add_argument("address", help="Contract address of the token to screen.")
    parser.add_argument("--chain", required=True, choices=sorted(config.GOPLUS_CHAIN_IDS.keys()),
                         help="Which chain the contract address is on.")
    parser.add_argument("--coingecko-id", default=None,
                         help="CoinGecko coin id, if known (skips the contract->id lookup).")
    args = parser.parse_args()

    result = resolve_and_screen(args.chain, args.address, args.coingecko_id)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

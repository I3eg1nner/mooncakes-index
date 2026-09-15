import argparse
import os
from itertools import zip_longest

from . import registry

STATS_URL = "https://mooncakes.io/api-new/v0/modules/statistics?raw=true"


def pick_hot(stats: list[tuple[str, int]], index: list[dict], top_n: int = 100) -> list[str]:
    known = {m["name"] for m in index}
    ranked = [name for name, _ in sorted(stats, key=lambda kv: -kv[1]) if name in known]
    ranked_set = set(ranked)
    rest = [m["name"] for m in index if m["name"] not in ranked_set]
    interleaved = [name for pair in zip_longest(ranked, rest) for name in pair if name is not None]
    return interleaved[:top_n]


def main() -> None:
    ap = argparse.ArgumentParser(prog="hotlist")
    ap.add_argument("--out", default="state/hotlist.txt")
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args()
    index = registry.fetch_module_index()
    try:
        data = registry.fetch_bytes(STATS_URL)
        stats = registry.parse_statistics_csv(data)
        print(f"statistics: {len(stats)} rows")
    except Exception as e:  # noqa: BLE001
        stats = []
        print(f"WARNING: statistics fetch failed ({e}); falling back to index order")
    hot = pick_hot(stats, index, args.top)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(hot))
    print(f"hotlist: {len(hot)} -> {args.out}")


if __name__ == "__main__":
    main()

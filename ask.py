"""Interactive spare-parts lookup.

    python ask.py                 # interactive prompt
    python ask.py --debug         # also show route, SQL mode, scores, chunk IDs
    python ask.py "spacer"        # one question, then exit
    python ask.py --no-llm ...    # retrieval only, no Claude call
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from parts_rag.retriever import Result, retrieve  # noqa: E402

BANNER = (
    "Spare Parts Lookup - Pulsar N-125 (00JZF7ZZ), "
    "28. Front Wheel Assembly - Disc Brake\n"
    "Ask by Part No. (e.g. Dh201079), diagram number (e.g. part 13), "
    "or description (e.g. spacer). Type 'exit' to quit."
)


def print_rows(result: Result) -> None:
    rows = result.rows
    if not rows:
        print("  (no matching rows)")
        return
    print(f"  {'Sr.':>3} | {'Part No.':<9} | {'Description':<40} | Qty")
    print(f"  {'-' * 3}-+-{'-' * 9}-+-{'-' * 40}-+-----")
    for h in rows:
        m = h.metadata
        print(f"  {m['sr_no']:>3} | {m['part_no']:<9} | {m['description']:<40} | {m['qty']}")


def print_debug(result: Result) -> None:
    r = result.route
    print("\n[debug]")
    print(f"  route        : {r.mode}" + (f" (value={r.value!r})" if r.value else ""))
    if r.terms:
        print(f"  keyword terms: {r.terms}")
    print(f"  lookup mode  : {result.lookup_mode}")
    print(f"  whole-assembly question: {r.whole_assembly}")
    for n in result.notes:
        print(f"  note         : {n}")
    print("  hits:")
    for h in result.hits:
        sim = f"{h.similarity:.3f}" if h.similarity is not None else "  -  "
        kw = f"{h.matched_terms}" if h.matched_terms is not None else "-"
        print(f"    {h.id:<12} source={h.source:<15} sim={sim} kw_terms={kw}")


def handle(query: str, debug: bool, use_llm: bool) -> None:
    result = retrieve(query)
    if use_llm:
        import anthropic
        from parts_rag.llm import answer

        try:
            ans = answer(result)
        except anthropic.AuthenticationError:
            print("Claude: invalid ANTHROPIC_API_KEY. Showing retrieved rows only.")
            ans = None
        except anthropic.NotFoundError:
            print("Claude: model not found. Check CLAUDE_MODEL in .env. Showing rows only.")
            ans = None
        except anthropic.RateLimitError:
            print("Claude: rate limited. Showing retrieved rows only.")
            ans = None
        except anthropic.APIStatusError as e:
            print(f"Claude API error ({e.status_code}). Showing retrieved rows only.")
            ans = None
        except anthropic.APIConnectionError:
            print("Claude: network error. Showing retrieved rows only.")
            ans = None
        if ans:
            print(f"\n{ans.text}\n")
            if not ans.casing_ok:
                print(f"  WARNING: answer contains part codes not in the catalogue "
                      f"rows (check casing): {ans.unknown_codes}")
    else:
        for n in result.notes:
            print(f"  {n}")
    print_rows(result)
    if debug:
        print_debug(result)
        if use_llm and ans:
            print(f"  model        : {ans.model} (stop_reason={ans.stop_reason})")
            print(f"  casing check : {'OK' if ans.casing_ok else 'FAILED ' + str(ans.unknown_codes)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="*", help="ask one question and exit")
    parser.add_argument("--debug", action="store_true", help="show retrieval details")
    parser.add_argument("--no-llm", action="store_true", help="skip the Claude call")
    args = parser.parse_args()
    use_llm = not args.no_llm

    if args.query:
        handle(" ".join(args.query), args.debug, use_llm)
        return 0

    print(BANNER)
    while True:
        try:
            query = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            return 0
        handle(query, args.debug, use_llm)


if __name__ == "__main__":
    raise SystemExit(main())

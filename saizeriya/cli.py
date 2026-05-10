import argparse

from .io import load_menu
from .optimizer import optimize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Saizeriya menu optimizer")
    parser.add_argument("--menu", required=True, help="Path to menu CSV")
    parser.add_argument("--budget", required=True, type=int, help="Budget in yen")
    parser.add_argument("--top", default=1, type=int, help="Number of plans to show")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    menu = load_menu(args.menu)
    plans = optimize(menu, budget=args.budget, top_n=args.top)

    if not plans:
        print("No feasible plan.")
        return

    for i, plan in enumerate(plans, start=1):
        names = ", ".join(item.name for item in plan.items) or "(empty)"
        print(f"#{i}: {plan.total_price}円 / score={plan.total_score:.2f}")
        print(f"  {names}")


if __name__ == "__main__":
    main()

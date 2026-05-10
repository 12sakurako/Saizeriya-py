from .model import MenuItem, Plan


def optimize(menu: list[MenuItem], budget: int, top_n: int = 1) -> list[Plan]:
    if budget < 0:
        raise ValueError("budget must be >= 0")
    if top_n <= 0:
        raise ValueError("top_n must be >= 1")

    # 0/1 knapsack with reconstruction-friendly states.
    best_by_price: list[tuple[float, tuple[int, ...]] | None] = [None] * (budget + 1)
    best_by_price[0] = (0.0, ())

    for idx, item in enumerate(menu):
        for price in range(budget, item.price - 1, -1):
            prev = best_by_price[price - item.price]
            if prev is None:
                continue
            cand_score = prev[0] + item.score
            cand_ix = prev[1] + (idx,)

            current = best_by_price[price]
            if current is None or cand_score > current[0]:
                best_by_price[price] = (cand_score, cand_ix)

    plans: list[Plan] = []
    for total_price, state in enumerate(best_by_price):
        if state is None:
            continue
        score, indices = state
        items = tuple(menu[i] for i in indices)
        plans.append(Plan(items=items, total_price=total_price, total_score=score))

    plans.sort(key=lambda p: (p.total_score, p.total_price), reverse=True)

    unique: list[Plan] = []
    seen: set[tuple[str, ...]] = set()
    for p in plans:
        key = tuple(sorted(i.name for i in p.items))
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
        if len(unique) >= top_n:
            break

    return unique

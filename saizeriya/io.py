import csv
from pathlib import Path

from .model import MenuItem


def load_menu(path: str | Path) -> list[MenuItem]:
    items: list[MenuItem] = []
    with Path(path).open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"name", "price", "score"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required.difference(set(reader.fieldnames or []))
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")

        for row in reader:
            items.append(
                MenuItem(
                    name=row["name"].strip(),
                    price=int(row["price"]),
                    score=float(row["score"]),
                )
            )
    return items

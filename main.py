#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

PageKind = Literal["number", "menu", "main", "account", "receipt", "history", "order", "unknown"]


@dataclass
class CartItem:
    id: str
    count: int = 1
    reorder: int = 0
    mod_id: str = ""
    mod_count: int = 0
    name: str | None = None
    price: int | None = None


@dataclass
class ClientState:
    baseURL: str
    nextId: str
    shopId: int
    tableNo: int
    peopleCount: int
    token: str | None = None
    sessionId: str | None = None
    pageKind: PageKind = "unknown"
    cart: list[CartItem] = field(default_factory=list)


class QueueLocker:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    def run(self, fn):
        with self._lock:
            return fn()


class SaizeriyaClient:
    def __init__(self, qr_url: str, people_count: int | None = None) -> None:
        self.session = requests.Session()
        self.locker = QueueLocker()
        self.state = self._init_from_qr(qr_url, people_count)

    def _init_from_qr(self, qr_url: str, people_count: int | None) -> ClientState:
        r = self.session.get(qr_url, allow_redirects=True, timeout=20)
        r.raise_for_status()
        final = r.url
        p = urlparse(final)
        qs = parse_qs(p.query)
        next_id = p.query
        shop_id = int(qs.get("sid", ["0"])[0])
        table_no = int(qs.get("tbl", [qs.get("tno", ["0"])[0]])[0])
        pc = int(qs.get("num", [str(people_count or 0)])[0])
        base_url = f"{p.scheme}://{p.netloc}{p.path}"
        state = ClientState(base_url, next_id, shop_id, table_no, pc, pageKind="unknown")
        self._refresh_from_html(r.text)
        return state

    def _page_url(self) -> str:
        return f"{self.state.baseURL}?{self.state.nextId}"

    def _command_url(self, path: str) -> str:
        return urljoin(self.state.baseURL, path)

    def _refresh_from_html(self, html: str) -> None:
        soup = BeautifulSoup(html, "html.parser")
        token = soup.select_one('input[name="token"]')
        ssid = soup.select_one('input[name="ssid"]')
        number = soup.select_one('input[name="number"]')
        form = soup.select_one("form[action]")
        if token and token.get("value"):
            self.state.token = token["value"]
        if ssid and ssid.get("value"):
            self.state.sessionId = ssid["value"]
        if number and number.get("value", "").isdigit():
            self.state.peopleCount = int(number["value"])
        if form and form.get("action"):
            q = urlparse(form["action"]).query
            if q:
                self.state.nextId = q
        proc = soup.select_one('input[name="proc"]')
        self.state.pageKind = (proc.get("value") if proc else "unknown") or "unknown"

    def _require_token(self) -> str:
        if not self.state.token:
            raise ValueError("Token not found. Move to a token-bearing page first.")
        return self.state.token

    def _submit_page(self, fields: dict[str, Any]) -> None:
        r = self.session.post(self._page_url(), data=fields, timeout=20)
        r.raise_for_status()
        self._refresh_from_html(r.text)

    def _post_json(self, path: str, fields: dict[str, Any]) -> dict[str, Any]:
        r = self.session.post(self._command_url(path), data=fields, timeout=20)
        r.raise_for_status()
        return r.json()

    def get_state(self) -> dict[str, Any]:
        d = asdict(self.state)
        d["cart"] = [asdict(c) for c in self.state.cart]
        return d

    def set_people_count(self, count: int) -> dict[str, Any]:
        def _run():
            if count < 1 or count > 99:
                raise ValueError("People count must be 1..99")
            self._submit_page({"proc": "number", "ctrl": "forced"})
            self._submit_page({"proc": "menu", "token": self._require_token(), "ctrl": "number", "number": count})
            self.state.peopleCount = count
            return self.get_state()
        return self.locker.run(_run)

    def lookup_item(self, code: str) -> dict[str, Any]:
        if not re.fullmatch(r"\d{4}", code):
            raise ValueError("Item code must be 4 digits")
        return self._post_json("./src/cmd/get_item.php", {"sid": self.state.shopId, "tno": self.state.tableNo, "lng": "1", "id": code, "num": self.state.peopleCount, "ssid": self.state.sessionId or ""})

    def add_item(self, code: str, count: int = 1, mod_id: str = "", mod_count: int = 0, reorder: bool = False) -> dict[str, Any]:
        def _run():
            if not re.fullmatch(r"\d{4}", code):
                raise ValueError("Item code must be 4 digits")
            item = self.lookup_item(code)
            data = item.get("item_data")
            if item.get("result") != "OK" or not data:
                raise ValueError(f"Item {code} not found")
            if data.get("state") == 0:
                raise ValueError(f"Item {code} is sold out")
            self._submit_page({"proc": "main", "token": self._require_token(), "ctrl": "add", "ord-drkbar-cnt": "0", "is_reorder": "1" if reorder else "0", "order-time": int(time.time()), "code": code, "amount": count, "mod_code": mod_id, "mod_amount": mod_count})
            self.state.cart.append(CartItem(id=code, count=count, reorder=1 if reorder else 0, mod_id=mod_id, mod_count=mod_count, name=data.get("name"), price=data.get("price")))
            return self.get_state()
        return self.locker.run(_run)

    def submit_order(self) -> dict[str, Any]:
        def _run():
            if not self.state.cart:
                raise ValueError("Cart is empty")
            body: list[tuple[str, Any]] = [("proc", "order"), ("token", self._require_token())]
            for i in self.state.cart:
                body += [("item[id][]", i.id), ("item[reorder][]", i.reorder), ("item[count][]", i.count), ("item[mod_id][]", i.mod_id), ("item[mod_count][]", i.mod_count)]
            r = self.session.post(self._page_url(), data=body, timeout=20)
            r.raise_for_status()
            self._refresh_from_html(r.text)
            self.state.cart.clear()
            return self.get_state()
        return self.locker.run(_run)




class MenuDB:
    def __init__(self, db_path: str = "menu.db", sql_path: str = "menu.sql") -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists() and Path(sql_path).exists():
            self._bootstrap(sql_path)

    def _bootstrap(self, sql_path: str) -> None:
        con = sqlite3.connect(self.db_path)
        try:
            con.executescript(Path(sql_path).read_text(encoding="utf-8"))
            con.commit()
        finally:
            con.close()

    def find(self, keyword: str) -> list[dict[str, Any]]:
        if not self.db_path.exists():
            return []
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        try:
            cur = con.execute(
                "SELECT id,name,name_en,price,price_with_tax,is_alcohol FROM menus WHERE CAST(id as TEXT)=? OR name LIKE ? OR name_en LIKE ? ORDER BY id LIMIT 30",
                (keyword, f"%{keyword}%", f"%{keyword}%"),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            con.close()


def run_server(client: SaizeriyaClient, menu_db: MenuDB, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def _json(self, code: int, payload: dict[str, Any] | list[Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            p = urlparse(self.path)
            q = parse_qs(p.query)
            try:
                if p.path == "/health":
                    return self._json(200, {"ok": True})
                if p.path == "/state":
                    return self._json(200, client.get_state())
                if p.path == "/menu":
                    keyword = q.get("q", [""])[0]
                    return self._json(200, menu_db.find(keyword) if keyword else [])
                self._json(404, {"error": "not found"})
            except Exception as e:
                self._json(500, {"error": str(e)})

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Server listening on http://{host}:{port}")
    server.serve_forever()
def main() -> int:
    parser = argparse.ArgumentParser(description="Saizeriya CLI (Python)")
    parser.add_argument("qr_url")
    parser.add_argument("command", nargs="?", default="state")
    parser.add_argument("--menu-db", default="menu.db")
    parser.add_argument("--menu-sql", default="menu.sql")
    parser.add_argument("args", nargs="*")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=80)
    ns = parser.parse_args()
    c = SaizeriyaClient(ns.qr_url)
    mdb = MenuDB(ns.menu_db, ns.menu_sql)
    cmd = ns.command
    a = ns.args
    if cmd == "state":
        print(json.dumps(c.get_state(), ensure_ascii=False, indent=2))
    elif cmd == "people":
        print(json.dumps(c.set_people_count(int(a[0])), ensure_ascii=False, indent=2))
    elif cmd == "lookup":
        print(json.dumps(c.lookup_item(a[0]), ensure_ascii=False, indent=2))
    elif cmd == "add":
        print(json.dumps(c.add_item(a[0], int(a[1]) if len(a) > 1 else 1), ensure_ascii=False, indent=2))
    elif cmd == "submit":
        print(json.dumps(c.submit_order(), ensure_ascii=False, indent=2))
    elif cmd == "menu":
        print(json.dumps(mdb.find(a[0]), ensure_ascii=False, indent=2))
    elif cmd == "serve":
        run_server(c, mdb, ns.host, ns.port)
    else:
        raise ValueError(f"Unknown command: {cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

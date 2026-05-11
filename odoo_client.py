from __future__ import annotations

import os
import xmlrpc.client
from dataclasses import dataclass
from typing import Any


@dataclass
class SaleOrder:
    odoo_id: int
    name: str
    partner_id: int
    partner_name: str
    state: str
    date_order: str
    amount_untaxed: float
    amount_tax: float
    amount_total: float
    write_date: str


@dataclass
class SaleOrderLine:
    odoo_id: int
    order_id: int
    order_name: str
    product_id: int
    product_name: str
    product_code: str
    qty: float
    price_unit: float
    cost: float
    price_subtotal: float
    write_date: str


@dataclass
class StockQuant:
    odoo_id: int
    product_id: int
    product_name: str
    product_code: str
    location_id: int
    location_name: str
    quantity: float
    reserved_quantity: float
    write_date: str


class OdooClient:
    """
    Connects to Odoo via XML-RPC using an API key.
    Works with Odoo Online (*.odoo.com) and self-hosted instances.
    """

    FIELDS = [
        "id",
        "product_id",
        "location_id",
        "quantity",
        "reserved_quantity",
        "write_date",
    ]

    def __init__(self, url: str, db: str, username: str, api_key: str):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.api_key = api_key
        self._uid: int | None = None

    @classmethod
    def from_env(cls) -> "OdooClient":
        return cls(
            url=_require_env("ODOO_URL"),
            db=_require_env("ODOO_DB"),
            username=_require_env("ODOO_USERNAME"),
            api_key=_require_env("ODOO_API_KEY"),
        )

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_uid(self) -> int:
        if self._uid is None:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self._uid = common.authenticate(self.db, self.username, self.api_key, {})
            if not self._uid:
                raise ConnectionError(
                    "Odoo authentication failed. Check ODOO_USERNAME and ODOO_API_KEY."
                )
        return self._uid

    def _models(self) -> xmlrpc.client.ServerProxy:
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_sale_orders(
        self,
        domain: list | None = None,
        limit: int = 0,
    ) -> list[SaleOrder]:
        """Fetch sale.order records (quotations + confirmed orders)."""
        if domain is None:
            domain = [("state", "!=", "cancel")]

        uid = self._get_uid()
        models = self._models()

        kwargs: dict[str, Any] = {
            "fields": ["id", "name", "partner_id", "state", "date_order",
                       "amount_untaxed", "amount_tax", "amount_total", "write_date"],
        }
        if limit:
            kwargs["limit"] = limit

        raw: list[dict] = models.execute_kw(
            self.db, uid, self.api_key,
            "sale.order", "search_read",
            [domain],
            kwargs,
        )

        return [_parse_sale_order(r) for r in raw]

    def get_sale_order_lines(
        self,
        domain: list | None = None,
        limit: int = 0,
    ) -> list[SaleOrderLine]:
        """Fetch sale.order.line records."""
        if domain is None:
            domain = [("order_id.state", "!=", "cancel")]

        uid = self._get_uid()
        models = self._models()

        kwargs: dict[str, Any] = {
            "fields": ["id", "order_id", "product_id",
                       "product_uom_qty", "price_unit", "price_subtotal", "write_date"],
        }
        if limit:
            kwargs["limit"] = limit

        raw: list[dict] = models.execute_kw(
            self.db, uid, self.api_key,
            "sale.order.line", "search_read",
            [domain],
            kwargs,
        )

        product_ids = list({r["product_id"][0] for r in raw if r.get("product_id")})
        cost_map: dict[int, float] = {}
        if product_ids:
            products = models.execute_kw(
                self.db, uid, self.api_key,
                "product.product", "read",
                [product_ids],
                {"fields": ["id", "standard_price"]},
            )
            cost_map = {p["id"]: float(p.get("standard_price") or 0) for p in products}

        return [_parse_sale_order_line(r, cost_map) for r in raw]

    def get_stock_quants(
        self,
        domain: list | None = None,
        limit: int = 0,
    ) -> list[StockQuant]:
        """
        Fetch stock.quant records.

        domain  – Odoo domain filter, defaults to all internal locations.
        limit   – 0 means no limit.
        """
        if domain is None:
            # Only internal locations (excludes virtual/scrap/customer locations)
            domain = [("location_id.usage", "=", "internal")]

        uid = self._get_uid()
        models = self._models()

        kwargs: dict[str, Any] = {"fields": self.FIELDS}
        if limit:
            kwargs["limit"] = limit

        raw: list[dict] = models.execute_kw(
            self.db, uid, self.api_key,
            "stock.quant", "search_read",
            [domain],
            kwargs,
        )

        return [_parse_quant(r) for r in raw]


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

def _parse_sale_order(raw: dict) -> SaleOrder:
    partner = raw.get("partner_id") or [0, ""]
    return SaleOrder(
        odoo_id=raw["id"],
        name=str(raw.get("name") or ""),
        partner_id=partner[0],
        partner_name=partner[1] if len(partner) > 1 else "",
        state=str(raw.get("state") or ""),
        date_order=str(raw.get("date_order") or ""),
        amount_untaxed=float(raw.get("amount_untaxed") or 0),
        amount_tax=float(raw.get("amount_tax") or 0),
        amount_total=float(raw.get("amount_total") or 0),
        write_date=str(raw.get("write_date") or ""),
    )


def _parse_sale_order_line(raw: dict, cost_map: dict[int, float] | None = None) -> SaleOrderLine:
    order = raw.get("order_id") or [0, ""]
    product = raw.get("product_id") or [0, ""]
    product_display: str = product[1] if len(product) > 1 else ""
    code, name = _split_product_display(product_display)
    product_id = product[0]
    return SaleOrderLine(
        odoo_id=raw["id"],
        order_id=order[0],
        order_name=order[1] if len(order) > 1 else "",
        product_id=product_id,
        product_name=name,
        product_code=code,
        qty=float(raw.get("product_uom_qty") or 0),
        price_unit=float(raw.get("price_unit") or 0),
        cost=(cost_map or {}).get(product_id, 0.0),
        price_subtotal=float(raw.get("price_subtotal") or 0),
        write_date=str(raw.get("write_date") or ""),
    )


def _parse_quant(raw: dict) -> StockQuant:
    product = raw.get("product_id") or [0, ""]
    location = raw.get("location_id") or [0, ""]

    # product_id is [id, "CODE NAME"] — split code from name if present
    product_display: str = product[1] if len(product) > 1 else ""
    code, name = _split_product_display(product_display)

    return StockQuant(
        odoo_id=raw["id"],
        product_id=product[0],
        product_name=name,
        product_code=code,
        location_id=location[0],
        location_name=location[1] if len(location) > 1 else "",
        quantity=float(raw.get("quantity") or 0),
        reserved_quantity=float(raw.get("reserved_quantity") or 0),
        write_date=str(raw.get("write_date") or ""),
    )


def _split_product_display(display: str) -> tuple[str, str]:
    """
    Odoo returns product_id display as "[CODE] Name" or just "Name".
    Returns (code, name).
    """
    if display.startswith("["):
        end = display.find("]")
        if end != -1:
            code = display[1:end].strip()
            name = display[end + 1:].strip()
            return code, name
    return "", display


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val

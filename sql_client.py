from __future__ import annotations

import os
import pymssql

from odoo_client import StockQuant, SaleOrder, SaleOrderLine


CREATE_SALE_ORDER_SQL = """
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'sale_order'
)
BEGIN
    CREATE TABLE sale_order (
        odoo_id         INT           NOT NULL PRIMARY KEY,
        name            NVARCHAR(100) NOT NULL,
        partner_id      INT           NOT NULL,
        partner_name    NVARCHAR(255) NOT NULL,
        state           NVARCHAR(50)  NOT NULL,
        date_order      NVARCHAR(50)  NOT NULL,
        amount_untaxed  FLOAT         NOT NULL,
        amount_tax      FLOAT         NOT NULL,
        amount_total    FLOAT         NOT NULL,
        odoo_write_date NVARCHAR(50)  NOT NULL,
        synced_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
"""

CREATE_SALE_ORDER_LINE_SQL = """
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'sale_order_line'
)
BEGIN
    CREATE TABLE sale_order_line (
        odoo_id         INT           NOT NULL PRIMARY KEY,
        order_id        INT           NOT NULL,
        order_name      NVARCHAR(100) NOT NULL,
        product_id      INT           NOT NULL,
        product_name    NVARCHAR(255) NOT NULL,
        product_code    NVARCHAR(100) NOT NULL,
        qty             FLOAT         NOT NULL,
        price_unit      FLOAT         NOT NULL,
        cost            FLOAT         NOT NULL,
        price_subtotal  FLOAT         NOT NULL,
        odoo_write_date NVARCHAR(50)  NOT NULL,
        synced_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
"""

UPSERT_SALE_ORDER_SQL = """
MERGE sale_order AS target
USING (VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)) AS source (
    odoo_id, name, partner_id, partner_name,
    state, date_order,
    amount_untaxed, amount_tax, amount_total, odoo_write_date
)
ON target.odoo_id = source.odoo_id
WHEN MATCHED THEN
    UPDATE SET
        name            = source.name,
        partner_id      = source.partner_id,
        partner_name    = source.partner_name,
        state           = source.state,
        date_order      = source.date_order,
        amount_untaxed  = source.amount_untaxed,
        amount_tax      = source.amount_tax,
        amount_total    = source.amount_total,
        odoo_write_date = source.odoo_write_date,
        synced_at       = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (
        odoo_id, name, partner_id, partner_name,
        state, date_order,
        amount_untaxed, amount_tax, amount_total, odoo_write_date
    )
    VALUES (
        source.odoo_id, source.name, source.partner_id, source.partner_name,
        source.state, source.date_order,
        source.amount_untaxed, source.amount_tax, source.amount_total, source.odoo_write_date
    );
"""

UPSERT_SALE_ORDER_LINE_SQL = """
MERGE sale_order_line AS target
USING (VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)) AS source (
    odoo_id, order_id, order_name,
    product_id, product_name, product_code,
    qty, price_unit, cost, price_subtotal, odoo_write_date
)
ON target.odoo_id = source.odoo_id
WHEN MATCHED THEN
    UPDATE SET
        order_id        = source.order_id,
        order_name      = source.order_name,
        product_id      = source.product_id,
        product_name    = source.product_name,
        product_code    = source.product_code,
        qty             = source.qty,
        price_unit      = source.price_unit,
        cost            = source.cost,
        price_subtotal  = source.price_subtotal,
        odoo_write_date = source.odoo_write_date,
        synced_at       = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (
        odoo_id, order_id, order_name,
        product_id, product_name, product_code,
        qty, price_unit, cost, price_subtotal, odoo_write_date
    )
    VALUES (
        source.odoo_id, source.order_id, source.order_name,
        source.product_id, source.product_name, source.product_code,
        source.qty, source.price_unit, source.cost, source.price_subtotal, source.odoo_write_date
    );
"""

CREATE_TABLE_SQL = """
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'inventory_stock'
)
BEGIN
    CREATE TABLE inventory_stock (
        odoo_id            INT           NOT NULL PRIMARY KEY,
        product_id         INT           NOT NULL,
        product_name       NVARCHAR(255) NOT NULL,
        product_code       NVARCHAR(100) NOT NULL,
        location_id        INT           NOT NULL,
        location_name      NVARCHAR(255) NOT NULL,
        quantity           FLOAT         NOT NULL,
        reserved_quantity  FLOAT         NOT NULL,
        odoo_write_date    NVARCHAR(50)  NOT NULL,
        synced_at          DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    );
END
"""

UPSERT_SQL = """
MERGE inventory_stock AS target
USING (VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)) AS source (
    odoo_id, product_id, product_name, product_code,
    location_id, location_name,
    quantity, reserved_quantity, odoo_write_date
)
ON target.odoo_id = source.odoo_id
WHEN MATCHED THEN
    UPDATE SET
        product_id        = source.product_id,
        product_name      = source.product_name,
        product_code      = source.product_code,
        location_id       = source.location_id,
        location_name     = source.location_name,
        quantity          = source.quantity,
        reserved_quantity = source.reserved_quantity,
        odoo_write_date   = source.odoo_write_date,
        synced_at         = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (
        odoo_id, product_id, product_name, product_code,
        location_id, location_name,
        quantity, reserved_quantity, odoo_write_date
    )
    VALUES (
        source.odoo_id, source.product_id, source.product_name, source.product_code,
        source.location_id, source.location_name,
        source.quantity, source.reserved_quantity, source.odoo_write_date
    );
"""


class SqlClient:
    def __init__(self, server: str, database: str, username: str, password: str):
        self._server = server
        self._database = database
        self._username = username
        self._password = password

    @classmethod
    def from_env(cls) -> "SqlClient":
        return cls(
            server=_require_env("SQL_SERVER"),
            database=_require_env("SQL_DATABASE"),
            username=_require_env("SQL_USERNAME"),
            password=_require_env("SQL_PASSWORD"),
        )

    def _connect(self):
        return pymssql.connect(
            server=self._server,
            user=self._username,
            password=self._password,
            database=self._database,
            tds_version="7.4",
        )

    # ------------------------------------------------------------------

    def ensure_table(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_TABLE_SQL)
            conn.commit()

    def ensure_sale_tables(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_SALE_ORDER_SQL)
            cursor.execute(CREATE_SALE_ORDER_LINE_SQL)
            conn.commit()

    def upsert_sale_orders(self, records: list[SaleOrder]) -> int:
        if not records:
            return 0
        rows = [
            (
                r.odoo_id, r.name, r.partner_id, r.partner_name,
                r.state, r.date_order,
                r.amount_untaxed, r.amount_tax, r.amount_total, r.write_date,
            )
            for r in records
        ]
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executemany(UPSERT_SALE_ORDER_SQL, rows)
            conn.commit()
        return len(rows)

    def upsert_sale_order_lines(self, records: list[SaleOrderLine]) -> int:
        if not records:
            return 0
        rows = [
            (
                r.odoo_id, r.order_id, r.order_name,
                r.product_id, r.product_name, r.product_code,
                r.qty, r.price_unit, r.cost, r.price_subtotal, r.write_date,
            )
            for r in records
        ]
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executemany(UPSERT_SALE_ORDER_LINE_SQL, rows)
            conn.commit()
        return len(rows)

    def upsert_stock_quants(self, records: list[StockQuant]) -> int:
        if not records:
            return 0

        rows = [
            (
                r.odoo_id,
                r.product_id,
                r.product_name,
                r.product_code,
                r.location_id,
                r.location_name,
                r.quantity,
                r.reserved_quantity,
                r.write_date,
            )
            for r in records
        ]

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executemany(UPSERT_SQL, rows)
            conn.commit()

        return len(rows)


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return val

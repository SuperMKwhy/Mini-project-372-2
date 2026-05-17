import logging
import azure.functions as func

from odoo_client import OdooClient
from sql_client import SqlClient

app = func.FunctionApp()


@app.function_name(name="SyncOrders")
@app.route(route="sync-orders", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def sync_orders(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("SyncOrders triggered.")

    try:
        odoo = OdooClient.from_env()
        orders = odoo.get_sale_orders()
        lines = odoo.get_sale_order_lines()
        logging.info(f"Fetched {len(orders)} sale orders, {len(lines)} order lines from Odoo.")

        sql = SqlClient.from_env()
        sql.ensure_sale_tables()
        upserted_orders = sql.upsert_sale_orders(orders)
        upserted_lines = sql.upsert_sale_order_lines(lines)
        logging.info(f"Upserted {upserted_orders} orders, {upserted_lines} lines into Azure SQL.")

        return func.HttpResponse(
            f"Done. Fetched {len(orders)} orders and {len(lines)} lines, "
            f"upserted {upserted_orders} orders and {upserted_lines} lines.",
            status_code=200,
        )

    except Exception as exc:
        logging.exception("SyncOrders failed.")
        return func.HttpResponse(f"Error: {exc}", status_code=500)


@app.function_name(name="SyncInventory")
@app.route(route="sync-inventory", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def sync_inventory(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("SyncInventory triggered.")

    try:
        odoo = OdooClient.from_env()
        records = odoo.get_stock_quants()
        logging.info(f"Fetched {len(records)} stock.quant records from Odoo.")

        sql = SqlClient.from_env()
        sql.ensure_table()
        upserted = sql.upsert_stock_quants(records)
        logging.info(f"Upserted {upserted} rows into Azure SQL.")

        return func.HttpResponse(
            f"Done. Fetched {len(records)} records, upserted {upserted} rows.",
            status_code=200,
        )

    except Exception as exc:
        logging.exception("SyncInventory failed.")
        return func.HttpResponse(f"Error: {exc}", status_code=500)


@app.function_name(name="IngestTransaction")
@app.route(route="ingest-transaction", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_transaction(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("IngestTransaction triggered.")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON body.", status_code=400)

    order_id = body.get("order_id")
    rfid_tag = body.get("rfid_tag")
    gas_type = body.get("gas_type")

    if not all([order_id, rfid_tag, gas_type]):
        return func.HttpResponse(
            "Missing required fields: order_id, rfid_tag, gas_type.",
            status_code=400,
        )

    try:
        sql = SqlClient.from_env()
        sql.ensure_gas_transaction_table()
        sql.insert_gas_transaction(
            order_id=str(order_id),
            rfid_tag=str(rfid_tag),
            gas_type=str(gas_type),
        )
        logging.info(f"Inserted gas_transaction: order_id={order_id}")
        return func.HttpResponse("OK", status_code=200)

    except Exception as exc:
        logging.exception("IngestTransaction failed.")
        return func.HttpResponse(f"Error: {exc}", status_code=500)

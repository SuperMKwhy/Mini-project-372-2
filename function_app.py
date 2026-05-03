import logging
import azure.functions as func

from odoo_client import OdooClient
from sql_client import SqlClient

app = func.FunctionApp()


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

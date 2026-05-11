import xmlrpc.client, json

with open("local.settings.json") as f:
    env = json.load(f)["Values"]

url      = env["ODOO_URL"]
db       = env["ODOO_DB"]
username = env["ODOO_USERNAME"]
api_key  = env["ODOO_API_KEY"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid    = common.authenticate(db, username, api_key, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

# Fetch one real sale order line to get a product_id
lines = models.execute_kw(db, uid, api_key, "sale.order.line", "search_read",
    [[]], {"fields": ["id", "product_id"], "limit": 1})
print("sample line:", lines)

product_id = lines[0]["product_id"][0]

# Read that product and look for cost fields
product = models.execute_kw(db, uid, api_key, "product.product", "read",
    [[product_id]], {"fields": ["id", "name", "standard_price", "lst_price"]})
print("product:", product)
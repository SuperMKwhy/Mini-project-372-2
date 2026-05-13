import xmlrpc.client, json, sys, datetime

class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, data):
        for f in self.files:
            f.write(data)
    def flush(self):
        for f in self.files:
            f.flush()

output_file = open(f"odoo_inspect_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", "w", encoding="utf-8")
sys.stdout = Tee(sys.__stdout__, output_file)

with open("local.settings.json") as f:
    env = json.load(f)["Values"]

url      = env["ODOO_URL"]
db       = env["ODOO_DB"]
username = env["ODOO_USERNAME"]
api_key  = env["ODOO_API_KEY"]

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid    = common.authenticate(db, username, api_key, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

MODELS_TO_INSPECT = [
    "product.product",
    "product.template",
    "sale.order",
    "sale.order.line",
    "purchase.order",
    "purchase.order.line",
    "stock.move",
    "account.move",
    "account.move.line",
]

def inspect_model(model_name):
    print(f"\n{'='*60}")
    print(f"MODEL: {model_name}")
    print('='*60)
    try:
        fields = models.execute_kw(db, uid, api_key, model_name, "fields_get",
            [], {"attributes": ["string", "type"]})
        for fname, finfo in sorted(fields.items()):
            print(f"  {fname:<40} [{finfo['type']:<12}] {finfo.get('string','')}")

        records = models.execute_kw(db, uid, api_key, model_name, "search_read",
            [[]], {"limit": 2})
        if records:
            print(f"\n  --- Sample record(s) ---")
            for rec in records:
                print(f"  {json.dumps(rec, indent=4, default=str)}")
        else:
            print(f"\n  (no records found)")
    except Exception as e:
        print(f"  ERROR: {e}")

for m in MODELS_TO_INSPECT:
    inspect_model(m)

output_file.close()
sys.stdout = sys.__stdout__
print(f"Results saved to {output_file.name}")

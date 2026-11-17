"""
Router modules for ERP System API
"""

# Import all router modules to make them available
from app.routers import bulk_import_export, migrations

# Stub routers - replace with actual implementations
class StubRouter:
    def __init__(self, prefix, tags):
        self.prefix = prefix
        self.tags = tags
        
    def get(self, path):
        def decorator(func):
            return func
        return decorator
    
    def post(self, path):
        def decorator(func):
            return func
        return decorator

# Create stub routers for missing modules
auth = type('obj', (object,), {'router': None})()
users = type('obj', (object,), {'router': None})()
roles = type('obj', (object,), {'router': None})()
permissions = type('obj', (object,), {'router': None})()
products = type('obj', (object,), {'router': None})()
inventory = type('obj', (object,), {'router': None})()
suppliers = type('obj', (object,), {'router': None})()
purchases = type('obj', (object,), {'router': None})()
sales = type('obj', (object,), {'router': None})()
customers = type('obj', (object,), {'router': None})()
orders = type('obj', (object,), {'router': None})()
invoices = type('obj', (object,), {'router': None})()
payments = type('obj', (object,), {'router': None})()
accounts = type('obj', (object,), {'router': None})()
reports = type('obj', (object,), {'router': None})()
analytics = type('obj', (object,), {'router': None})()
notifications = type('obj', (object,), {'router': None})()
settings = type('obj', (object,), {'router': None})()
audit_logs = type('obj', (object,), {'router': None})()
search = type('obj', (object,), {'router': None})()
llm = type('obj', (object,), {'router': None})()
activity_logs = type('obj', (object,), {'router': None})()
dashboard = type('obj', (object,), {'router': None})()

__all__ = [
    "auth",
    "users",
    "roles",
    "permissions",
    "products",
    "inventory",
    "suppliers",
    "purchases",
    "sales",
    "customers",
    "orders",
    "invoices",
    "payments",
    "accounts",
    "reports",
    "analytics",
    "notifications",
    "settings",
    "audit_logs",
    "bulk_import_export",
    "migrations",
    "search",
    "llm",
    "activity_logs",
    "dashboard"
]

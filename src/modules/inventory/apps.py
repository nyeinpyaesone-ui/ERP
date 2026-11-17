"""
Inventory Module Configuration
"""
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src.modules.inventory'
    verbose_name = 'Inventory Management'

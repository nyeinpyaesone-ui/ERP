"""
API URL Configuration
"""

from django.urls import path, include

app_name = 'api'

urlpatterns = [
    # Authentication endpoints
    # path('auth/', include('rest_framework_simplejwt.urls')),
    
    # Module API endpoints
    path('inventory/', include('src.modules.inventory.urls')),
    # path('hr/', include('src.modules.hr.api.urls')),
    # path('finance/', include('src.modules.finance.api.urls')),
    # path('sales/', include('src.modules.sales.api.urls')),
    # path('procurement/', include('src.modules.procurement.api.urls')),
    # path('manufacturing/', include('src.modules.manufacturing.api.urls')),
]

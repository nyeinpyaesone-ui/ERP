"""
URL Configuration for ERP System
=================================
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/', include('src.api.urls')),
    
    # Module-specific URLs can be added here
    # path('inventory/', include('src.modules.inventory.urls')),
    # path('hr/', include('src.modules.hr.urls')),
    # path('finance/', include('src.modules.finance.urls')),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "ERP System Administration"
admin.site.site_title = "ERP Admin"
admin.site.index_title = "Welcome to ERP System Administration"

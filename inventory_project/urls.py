# inventory_project/urls.py
from django.contrib import admin
from django.urls import path, include
from accounts.views import login_view,  logout_view, create_business, business_list  # Remove root_redirect
from inventory import views
from inventory.dashboard_views import manager_dashboard, cashier_dashboard
from inventory.views import add_stock_page,manage_categories
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', login_view, name='login'),
    path('accounts/logout/', logout_view, name='logout'),
    path('accounts/create-business/', create_business, name='create_business'),
    path('accounts/businesses/', business_list, name='business_list'),
    path('manager/', manager_dashboard, name='manager_dashboard'),
    path('cashier/', cashier_dashboard, name='cashier_dashboard'),
    path('inventory/', include('inventory.urls')),
    path('', login_view, name='root'),
    path('manage-categories/', manage_categories, name='manage_categories'),
    path('add-stock/', add_stock_page, name='add_stock_page') # Use login_view for root URL
]

# Static files
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# dashboards/urls.py
from sys import path
from django.urls import path
from inventory.dashboard_views import manager_dashboard, cashier_dashboard, store_dashboard

urlpatterns = [
    path('manager/', manager_dashboard, name='manager_dashboard'),
    path('cashier/', cashier_dashboard, name='cashier_dashboard'),
    path('store/', store_dashboard, name='store_dashboard'),
]
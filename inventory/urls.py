from django.urls import path
from . import views

urlpatterns = [
    path('create-sale/', views.create_sale, name='create_sale'),
    path('receipt/<int:sale_id>/', views.receipt, name='receipt'),
    path('restock/', views.restock_product, name='restock'),
     path('sales/', views.sale_list, name='sale_list'),
]
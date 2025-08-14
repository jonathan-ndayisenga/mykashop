from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models import Sum, F, Count


from accounts import models
from .models import Sale, SaleItem, Product, Restock, Category
from accounts.models import Business
from .forms import SaleForm, SaleItemForm

from django.contrib.auth import get_user_model

User = get_user_model()

# Decorators
def manager_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_manager():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper

def cashier_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_cashier():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
@cashier_required
def create_sale(request):
    business = request.user.business
    if not business:
        return redirect('business_settings')
    
    if request.method == 'POST':
        with transaction.atomic():
            sale = Sale(business=business, created_by=request.user)
            sale.save()
            
            product_ids = request.POST.getlist('product')
            quantities = request.POST.getlist('quantity')
            
            total_amount = 0
            
            for product_id, quantity in zip(product_ids, quantities):
                if not product_id or not quantity:
                    continue
                
                product = get_object_or_404(Product, id=product_id, business=business)
                quantity = int(quantity)
                
                if quantity <= 0:
                    continue
                    
                if product.stock_quantity < quantity:
                    sale.delete()
                    return JsonResponse({
                        'success': False,
                        'error': f"Insufficient stock for {product.name}"
                    }, status=400)
                
                sale_item = SaleItem(
                    sale=sale,
                    product=product,
                    quantity=quantity,
                    unit_price=product.selling_price
                )
                sale_item.save()
                
                product.stock_quantity -= quantity
                product.save()
                
                total_amount += sale_item.total_price
            
            sale.total_amount = total_amount
            sale.save()
            
            return JsonResponse({
                'success': True,
                'redirect_url': f'/inventory/receipt/{sale.id}/'
            })
    
    products = Product.objects.filter(business=business)
    return render(request, 'inventory/create_sale.html', {'products': products})

@login_required
@cashier_required
def receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id, business=request.user.business)
    return render(request, 'inventory/receipt.html', {'sale': sale})

@login_required
@manager_required
def manager_dashboard(request):
    business = request.user.business
    if not business:
        return redirect('create_business')
    
    low_stock = Product.objects.filter(
        business=business,
        stock_quantity__lte=models.F('low_stock_threshold')
    )
    
    today_sales = Sale.objects.filter(
        business=business,
        created_at__date=timezone.now().date()
    ).aggregate(total=models.Sum('total_amount'))['total'] or 0
    
    context = {
        'low_stock_products': low_stock,
        'today_sales': today_sales,
        'total_products': Product.objects.filter(business=business).count(),
    }
    return render(request, 'dashboards/manager.html', context)

@login_required
@cashier_required
def cashier_dashboard(request):
    business = request.user.business
    if not business:
        return redirect('business_settings')
    
    today_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date=timezone.now().date()
    ).aggregate(
        total_sales=models.Sum('total_amount'),
        count=models.Count('id')
    )
    
    context = {
        'today_sales': today_sales['total_sales'] or 0,
        'sale_count': today_sales['count'] or 0,
    }
    return render(request, 'dashboards/cashier.html', context)

@login_required
@manager_required
def restock_product(request):
    business = request.user.business
    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity'))
        note = request.POST.get('note', '')
        
        product = get_object_or_404(Product, id=product_id, business=business)
        
        Restock.objects.create(
            product=product,
            quantity=quantity,
            restocked_by=request.user,
            note=note
        )
        return redirect('manager_dashboard')
    
    products = Product.objects.filter(business=business)
    return render(request, 'inventory/restock.html', {'products': products})

@login_required
def sale_list(request):
    business = request.user.business
    sales = Sale.objects.filter(business=business).order_by('-created_at')
    
    # Date filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        sales = sales.filter(created_at__date__gte=start_date)
    if end_date:
        sales = sales.filter(created_at__date__lte=end_date)
    
    # Calculate total sales
    total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'sales': sales,
        'total_sales': total_sales,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'inventory/sale_list.html', context)

@login_required
def receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id, business=request.user.business)
    return render(request, 'inventory/receipt.html', {'sale': sale})
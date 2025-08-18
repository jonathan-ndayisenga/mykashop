from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models import Sum, F, Count
from fastapi import logger
from .models import Category
from .decorators import manager_required  # 



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
    
    total_categories = Category.objects.filter(business=business).count()
    context = {
        'low_stock_products': low_stock,
        'today_sales': today_sales,
        'total_products': Product.objects.filter(business=business).count(),
        'total_categories': total_categories,
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
    
    # Time range filtering
    time_range = request.GET.get('time_range')
    today = timezone.now().date()
    
    if time_range == 'today':
        sales = sales.filter(created_at__date=today)
    elif time_range == 'week':
        week_start = today - timedelta(days=today.weekday())
        sales = sales.filter(created_at__date__gte=week_start)
    elif time_range == 'month':
        sales = sales.filter(created_at__month=today.month, created_at__year=today.year)
    elif time_range == 'year':
        sales = sales.filter(created_at__year=today.year)
    
    # Date range filtering
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
        'time_range': time_range,
    }
    return render(request, 'inventory/sale_list.html', context)

@login_required
@manager_required
def manage_categories(request):
    business = request.user.business

    # Handle category deletion via POST
    if request.method == 'POST' and 'delete_id' in request.POST:
        category_id = request.POST.get('delete_id')
        try:
            category = Category.objects.get(id=category_id, business=business)
            category.delete()
            return JsonResponse({'success': True})
        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # Handle category creation via POST
    elif request.method == 'POST' and 'name' in request.POST:
        name = request.POST.get('name')
        if name:
            try:
                Category.objects.create(
                    name=name,
                    business=business
                )
                messages.success(request, f'Category "{name}" created successfully!')
                return redirect('manage_categories')
            except IntegrityError:
                messages.error(request, f'A category with name "{name}" already exists!')

    # GET request – show categories
    categories = Category.objects.filter(business=business).order_by('name')
    return render(request, 'inventory/manage_categories.html', {
        'categories': categories
    })

@login_required
@manager_required
def add_stock_page(request):
    business = request.user.business
    categories = Category.objects.filter(business=business)
    
    if request.method == 'POST':
        try:
            # Create new product
            product = Product.objects.create(
                name=request.POST['name'],
                category_id=request.POST['category'],
                unit=request.POST['unit'],
                stock_quantity=int(request.POST['stock_quantity']),
                buying_price=Decimal(request.POST['buying_price']),
                selling_price=Decimal(request.POST['selling_price']),
                business=business,
                low_stock_threshold=int(request.POST['low_stock_threshold'] or 5)
            )
            
            messages.success(request, f'Product "{product.name}" added successfully!')
            return redirect('manager_dashboard')
            
        except KeyError as e:
            messages.error(request, f'Missing required field: {e}')
        except ValueError as e:
            messages.error(request, f'Invalid value: {e}')
        except Exception as e:
            messages.error(request, f'Error adding product: {e}')
    
    return render(request, 'inventory/add_stock.html', {
        'categories': categories
    })

@login_required
def receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id, business=request.user.business)
    return render(request, 'inventory/receipt.html', {'sale': sale})
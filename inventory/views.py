from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.db import IntegrityError
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models import Sum, F, Count
from .models import Category, StockLog, Sale, SaleItem, Product
from accounts.models import Business
from django.contrib.auth import get_user_model

User = get_user_model()

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
                    
                try:
                    product.log_stock_change(
                        action='sale',
                        quantity_change=-quantity,
                        user=request.user,
                        notes=f"Sold in sale #{sale.receipt_number}",
                        reference=sale.receipt_number
                    )
                    
                except ValidationError:
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
@manager_required
def stock_management(request):
    business = request.user.business
    categories = Category.objects.filter(business=business)
    products = Product.objects.filter(business=business)
    
    category_filter = request.GET.get('category')
    low_stock_only = request.GET.get('low_stock')
    search_query = request.GET.get('q')
    
    if category_filter:
        products = products.filter(category_id=category_filter)
    
    if low_stock_only:
        products = products.filter(stock_quantity__lte=F('low_stock_threshold'))
    
    if search_query:
        products = products.filter(name__icontains=search_query)
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    stock_logs = StockLog.objects.filter(product__business=business)
    
    if start_date:
        stock_logs = stock_logs.filter(created_at__date__gte=start_date)
    if end_date:
        stock_logs = stock_logs.filter(created_at__date__lte=end_date)
    
    total_stock_value = sum(product.get_stock_value() for product in products)
    total_low_stock = products.filter(stock_quantity__lte=F('low_stock_threshold')).count()
    
    context = {
        'products': products,
        'categories': categories,
        'stock_logs': stock_logs[:50],
        'total_stock_value': total_stock_value,
        'total_low_stock': total_low_stock,
        'category_filter': category_filter,
        'low_stock_only': low_stock_only,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'inventory/stock_management.html', context)

@login_required
@cashier_required
def receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id, business=request.user.business)
    return render(request, 'inventory/receipt.html', {'sale': sale})

@login_required
@manager_required
def stock_overview(request):
    business = request.user.business
    products = Product.objects.filter(business=business)
    
    context = {
        'products': products
    }
    return render(request, 'inventory/stock_overview.html', context)

@login_required
@manager_required
def restock_product(request):
    business = request.user.business
    
    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = int(request.POST.get('quantity'))
        buying_price = request.POST.get('buying_price')
        selling_price = request.POST.get('selling_price')
        supplier = request.POST.get('supplier', '')
        note = request.POST.get('note', '')
        
        product = get_object_or_404(Product, id=product_id, business=business)
        
        try:
            if buying_price:
                product.buying_price = Decimal(buying_price)
            if selling_price:
                product.selling_price = Decimal(selling_price)
            
            product.log_stock_change(
                action='restock',
                quantity_change=quantity,
                user=request.user,
                buying_price=product.buying_price,
                selling_price=product.selling_price,
                notes=f"Restocked from {supplier}. {note}",
                reference=f"RESTOCK-{timezone.now().strftime('%Y%m%d-%H%M%S')}"
            )
            
            messages.success(request, f'Restocked {quantity} units of {product.name}')
            return redirect('restock')
            
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error during restock: {str(e)}')
    
    products = Product.objects.filter(business=business)
    
    recent_restocks = StockLog.objects.filter(
        product__business=business,
        action='restock'
    ).select_related('product', 'created_by').order_by('-created_at')[:10]
    
    context = {
        'products': products,
        'recent_restocks': recent_restocks
    }
    
    return render(request, 'inventory/restock.html', context)

@login_required
@manager_required
def restock_history(request):
    business = request.user.business
    restocks = StockLog.objects.filter(
        product__business=business,
        action='restock'
    ).select_related('product', 'created_by').order_by('-created_at')
    
    context = {
        'restocks': restocks
    }
    return render(request, 'inventory/restock_history.html', context)

@login_required
@manager_required
def manager_dashboard(request):
    business = request.user.business
    if not business:
        return redirect('business_settings')

    now = timezone.now()
    today = now.date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)

    today_sales = Sale.objects.filter(business=business, created_at__date=today).aggregate(
        total_sales=Sum('total_amount'), count=Count('id')
    )
    weekly_sales = Sale.objects.filter(business=business, created_at__date__gte=week_ago).aggregate(
        total_sales=Sum('total_amount'), count=Count('id')
    )
    monthly_sales = Sale.objects.filter(business=business, created_at__date__gte=month_ago).aggregate(
        total_sales=Sum('total_amount'), count=Count('id')
    )
    yearly_sales = Sale.objects.filter(business=business, created_at__date__gte=year_ago).aggregate(
        total_sales=Sum('total_amount'), count=Count('id')
    )

    total_products = Product.objects.filter(business=business).count()
    low_stock_products = Product.objects.filter(business=business, stock_quantity__lte=F('low_stock_threshold')).count()
    total_categories = Category.objects.filter(business=business).count()

    recent_sales = Sale.objects.filter(business=business).order_by('-created_at')[:10]
    top_products = (
        SaleItem.objects.filter(sale__business=business)
        .values('product', 'product__name', 'product__category__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:10]
    )

    recent_restocks = StockLog.objects.filter(
        product__business=business,
        action='restock'
    ).order_by('-created_at')[:10]

    context = {
        'business': business,
        'today_sales': today_sales['total_sales'] or 0,
        'today_transactions': today_sales['count'] or 0,
        'weekly_sales': weekly_sales['total_sales'] or 0,
        'weekly_transactions': weekly_sales['count'] or 0,
        'monthly_sales': monthly_sales['total_sales'] or 0,
        'monthly_transactions': monthly_sales['count'] or 0,
        'yearly_sales': yearly_sales['total_sales'] or 0,
        'yearly_transactions': yearly_sales['count'] or 0,
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'total_categories': total_categories,
        'recent_sales': recent_sales,
        'top_products': top_products,
        'recent_restocks': recent_restocks,
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
        total_sales=Sum('total_amount'),
        count=Count('id')
    )
    
    context = {
        'today_sales': today_sales['total_sales'] or 0,
        'sale_count': today_sales['count'] or 0,
    }
    return render(request, 'dashboards/cashier.html', context)

@login_required
def sale_list(request):
    business = request.user.business
    sales = Sale.objects.filter(business=business).order_by('-created_at')
    
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
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        sales = sales.filter(created_at__date__gte=start_date)
    if end_date:
        sales = sales.filter(created_at__date__lte=end_date)
    
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
def sales_history(request):
    business = request.user.business
    sales = Sale.objects.filter(business=business).prefetch_related('items__product').order_by('-created_at')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    product_id = request.GET.get('product')
    
    if start_date:
        sales = sales.filter(created_at__date__gte=start_date)
    if end_date:
        sales = sales.filter(created_at__date__lte=end_date)
    if product_id:
        sales = sales.filter(items__product_id=product_id)
    
    total_sales = sales.aggregate(total=Sum('total_amount'))['total'] or 0
    total_items = SaleItem.objects.filter(sale__in=sales).aggregate(total=Sum('quantity'))['total'] or 0
    
    products = Product.objects.filter(business=business)
    
    context = {
        'sales': sales,
        'total_sales': total_sales,
        'total_items': total_items,
        'products': products,
        'start_date': start_date,
        'end_date': end_date,
        'product_id': product_id,
    }
    
    return render(request, 'inventory/sales_history.html', context)

@login_required
@manager_required
def manage_categories(request):
    business = request.user.business

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
            
        except Exception as e:
            messages.error(request, f'Error adding product: {e}')
    
    return render(request, 'inventory/add_stock.html', {
        'categories': categories
    })

@login_required
@manager_required
def check_stock(request):
    business = request.user.business
    if not business:
        return redirect('create_business')

    query = request.GET.get("q", "")

    if query:
        products = Product.objects.filter(
            business=business,
            name__icontains=query
        ).select_related("category")

        product_list = []
        for product in products:
            total_sold = SaleItem.objects.filter(product=product).aggregate(
                total_qty=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('unit_price'))
            )
            qty_sold = total_sold['total_qty'] or 0
            revenue = total_sold['total_revenue'] or 0
            profit = revenue - (qty_sold * product.buying_price)

            product_list.append({
                'id': product.id,
                'name': product.name,
                'unit': product.unit,
                'buying_price': product.buying_price,
                'selling_price': product.selling_price,
                'stock_quantity': product.stock_quantity,
                'low_stock_threshold': product.low_stock_threshold,
                'last_restocked': product.last_restocked,
                'total_sold': qty_sold,
                'revenue': revenue,
                'profit': profit,
                'category': product.category.name,
            })

        return render(request, 'inventory/check_stock.html', {
            'search_results': product_list,
            'query': query,
            'stock_data': []
        })

    categories = Category.objects.filter(business=business)
    stock_data = []
    
    for category in categories:
        products = Product.objects.filter(category=category, business=business)
        
        product_list = []
        for product in products:
            total_sold = SaleItem.objects.filter(product=product).aggregate(
                total_qty=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('unit_price'))
            )
            qty_sold = total_sold['total_qty'] or 0
            revenue = total_sold['total_revenue'] or 0
            profit = revenue - (qty_sold * product.buying_price)

            product_list.append({
                'id': product.id,
                'name': product.name,
                'unit': product.unit,
                'buying_price': product.buying_price,
                'selling_price': product.selling_price,
                'stock_quantity': product.stock_quantity,
                'low_stock_threshold': product.low_stock_threshold,
                'last_restocked': product.last_restocked,
                'total_sold': qty_sold,
                'revenue': revenue,
                'profit': profit,
            })

        stock_data.append({
            'category': category,
            'products': product_list
        })

    return render(request, 'inventory/check_stock.html', {
        'stock_data': stock_data,
        'query': query,
    })

@login_required
@manager_required
def stock_log(request):
    business = request.user.business
    stock_logs = StockLog.objects.filter(product__business=business).select_related('product', 'created_by').order_by('-created_at')
    
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    action = request.GET.get('action')
    
    if start_date:
        stock_logs = stock_logs.filter(created_at__date__gte=start_date)
    if end_date:
        stock_logs = stock_logs.filter(created_at__date__lte=end_date)
    if action:
        stock_logs = stock_logs.filter(action=action)
    
    context = {
        'stock_logs': stock_logs,
        'start_date': start_date,
        'end_date': end_date,
        'action': action,
    }
    
    return render(request, 'inventory/stock_log.html', context)
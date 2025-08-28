from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F
from django.utils import timezone
from datetime import timedelta

from inventory.views import cashier_required, manager_required
from .models import Product, Category, Sale, SaleItem, StockLog
from django.db.models import Sum, Count, F, Q



@login_required
@manager_required
def manager_dashboard(request):
    """Dashboard for managers with business overview"""
    business = request.user.business
    if not business:
        return redirect('create_business')

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)

    # Sales metrics
    today_sales = Sale.objects.filter(
        business=business,
        created_at__date=today
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    weekly_sales = Sale.objects.filter(
        business=business,
        created_at__date__gte=week_ago
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    monthly_sales = Sale.objects.filter(
        business=business,
        created_at__date__gte=month_ago
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    yearly_sales = Sale.objects.filter(
        business=business,
        created_at__date__gte=year_ago
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Inventory metrics
    low_stock_products = Product.objects.filter(
        business=business,
        stock_quantity__lte=F('low_stock_threshold')
    ).count()

    total_products = Product.objects.filter(business=business).count()
    total_categories = Category.objects.filter(business=business).count()

    # Recent sales
    recent_sales = Sale.objects.filter(business=business).order_by('-created_at')[:5]

    # Top selling products
    top_products = Product.objects.filter(
        business=business,
        sale_items__isnull=False
    ).annotate(
        total_sold=Sum('sale_items__quantity')
    ).order_by('-total_sold')[:5]

    # Recent restocks
    recent_restocks = StockLog.objects.filter(
        product__business=business,
        action='restock'
    ).select_related('product', 'created_by').order_by('-created_at')[:5]

    # Pass data to match template variable names
    recent_restocks_template = [
        {
            'product': r.product,
            'restocked_by': r.created_by,
            'quantity': r.quantity_change,
            'restocked_at': r.created_at
        } for r in recent_restocks
    ]

    categories = Category.objects.filter(business=business)

    context = {
        'business': business,
        'today_sales': today_sales,
        'weekly_sales': weekly_sales,
        'monthly_sales': monthly_sales,
        'yearly_sales': yearly_sales,
        'low_stock_products': low_stock_products,
        'total_products': total_products,
        'total_categories': total_categories,
        'recent_sales': recent_sales,
        'top_products': top_products,
        'recent_restocks': recent_restocks_template,
        'categories': categories,
        'today_transactions': Sale.objects.filter(business=business, created_at__date=today).count(),
        'weekly_transactions': Sale.objects.filter(business=business, created_at__date__gte=week_ago).count(),
        'monthly_transactions': Sale.objects.filter(business=business, created_at__date__gte=month_ago).count(),
        'yearly_transactions': Sale.objects.filter(business=business, created_at__date__gte=year_ago).count(),
    }

    return render(request, 'dashboard/manager_dashboard.html', context)



@login_required
@cashier_required
def cashier_dashboard(request):
    """Dashboard for cashiers with sales performance"""
    business = request.user.business
    if not business:
        return redirect('business_settings')

    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)

    # Sales aggregates
    today_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date=today
    ).aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id')
    )

    weekly_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date__gte=week_ago
    ).aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id')
    )

    monthly_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date__gte=month_ago
    ).aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id')
    )

    yearly_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date__gte=year_ago
    ).aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id')
    )

    # Recent transactions
    recent_sales = Sale.objects.filter(
        business=business,
        created_by=request.user
    ).order_by('-created_at')[:3]

    # Fast moving products (fix related name)
    fast_moving_products = Product.objects.filter(
        business=business,
        sale_items__sale__created_by=request.user
    ).annotate(
        sold_count=Sum('sale_items__quantity')
    ).order_by('-sold_count')[:5]

    context = {
        'today_sales': today_sales['total_sales'] or 0,
        'today_transactions': today_sales['total_transactions'] or 0,
        'weekly_sales': weekly_sales['total_sales'] or 0,
        'weekly_transactions': weekly_sales['total_transactions'] or 0,
        'monthly_sales': monthly_sales['total_sales'] or 0,
        'monthly_transactions': monthly_sales['total_transactions'] or 0,
        'yearly_sales': yearly_sales['total_sales'] or 0,
        'yearly_transactions': yearly_sales['total_transactions'] or 0,
        'recent_sales': recent_sales,
        'fast_moving_products': fast_moving_products,
    }

    return render(request, 'dashboard/cashier_dashboard.html', context)
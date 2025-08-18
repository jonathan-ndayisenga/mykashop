from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import timedelta, datetime
from django.core.exceptions import PermissionDenied

from inventory.views import cashier_required, manager_required
from .models import Product, Category, Sale, SaleItem, Restock
from accounts.models import User

# Permission decorators (unchanged)

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
    
    # Sales data
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
    
    # Top selling products (fixed related name)
    top_products = Product.objects.filter(
        business=business,
        sale_items__isnull=False
    ).annotate(
        total_sold=Sum('sale_items__quantity')
    ).order_by('-total_sold')[:5]
    
    # Recent restocks
    recent_restocks = Restock.objects.filter(
        product__business=business
    ).select_related('product', 'restocked_by').order_by('-restocked_at')[:5]
    
    # Categories
    categories = Category.objects.filter(business=business)
    
    context = {
        'today_sales': today_sales,
        'weekly_sales': weekly_sales,
        'monthly_sales': monthly_sales,
        'yearly_sales': yearly_sales,
        'low_stock_products': low_stock_products,
        'total_products': total_products,
        'total_categories': total_categories,
        'recent_sales': recent_sales,
        'top_products': top_products,
        'recent_restocks': recent_restocks,
        'categories': categories,
    }
    
    return render(request, 'dashboard/manager_dashboard.html', context)


@login_required
@cashier_required
def cashier_dashboard(request):
    """Dashboard for cashiers with sales performance"""
    business = request.user.business
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)  # Added yearly sales
    
    # Today's sales performance
    today_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date=today
    ).aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id')
    )
    
    # Weekly performance
    weekly_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date__gte=week_ago
    ).aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id')
    )
    
    # Monthly performance (added)
    monthly_sales = Sale.objects.filter(
        business=business,
        created_by=request.user,
        created_at__date__gte=month_ago
    ).aggregate(
        total_sales=Sum('total_amount'),
        total_transactions=Count('id')
    )
    
    # Yearly performance (added)
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
    ).order_by('-created_at')[:5]
    
    # Fast moving products (for this cashier)
    fast_moving = Product.objects.filter(
        business=business,
        saleitem__sale__created_by=request.user
    ).annotate(
        sold_count=Sum('saleitem__quantity')
    ).order_by('-sold_count')[:5]
    
    context = {
        'today_sales': today_sales['total_sales'] or 0,
        'today_transactions': today_sales['total_transactions'] or 0,
        'weekly_sales': weekly_sales['total_sales'] or 0,
        'weekly_transactions': weekly_sales['total_transactions'] or 0,
        'monthly_sales': monthly_sales['total_sales'] or 0,  # Added
        'monthly_transactions': monthly_sales['total_transactions'] or 0,  # Added
        'yearly_sales': yearly_sales['total_sales'] or 0,  # Added
        'yearly_transactions': yearly_sales['total_transactions'] or 0,  # Added
        'recent_sales': recent_sales,
        'fast_moving_products': fast_moving,
    }


    
    
    return render(request, 'dashboard/cashier_dashboard.html', context)
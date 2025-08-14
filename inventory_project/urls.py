from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required
from inventory.dashboard_views import manager_dashboard, cashier_dashboard
from accounts.views import login_view, logout_view, create_business, business_list, root_redirect
from inventory.dashboard_views import manager_dashboard, cashier_dashboard

# Create a view that redirects to the appropriate dashboard
@login_required
def role_based_redirect(request):
    if request.user.is_manager():
        return RedirectView.as_view(url='/manager/')(request)
    elif request.user.is_cashier():
        return RedirectView.as_view(url='/cashier/')(request)
    # Add a fallback for other user types
    return RedirectView.as_view(url='/accounts/login/')(request)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', login_view, name='login'),
    path('accounts/logout/', logout_view, name='logout'),
    path('accounts/create-business/', create_business, name='create_business'),
    path('accounts/businesses/', business_list, name='business_list'),
    path('manager/', manager_dashboard, name='manager_dashboard'),
    path('cashier/', cashier_dashboard, name='cashier_dashboard'),
    path('inventory/', include('inventory.urls')),
    path('', root_redirect),
]

# Only serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Business
from .forms import BusinessCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login as auth_login, logout
from django.db import transaction, IntegrityError
import re

User = get_user_model()

def is_superuser(user):
    return user.is_superuser

@login_required
@user_passes_test(is_superuser)
def create_business(request):
    if request.method == 'POST':
        form = BusinessCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    business = form.save()
                    messages.success(request, 'Business created successfully.')
                    return redirect('business_list')
            except IntegrityError:
                messages.error(request, 'Error creating business. Please try again.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = BusinessCreationForm()
    return render(request, 'accounts/create_business.html', {'form': form})

@login_required
@user_passes_test(is_superuser)
def business_list(request):
    businesses = Business.objects.all()
    return render(request, 'accounts/business_list.html', {'businesses': businesses})

# ADDED: Login view implementation
def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_redirect_url(request.user))
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if not hasattr(user, 'business') or not user.business:
                messages.error(request, 'Your account is not associated with a business')
                return render(request, 'accounts/login.html')
                
            auth_login(request, user)
            return redirect(get_redirect_url(user))
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'accounts/login.html')

# ADDED: Logout view implementation
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')

# ADDED: Redirect helper function
def get_redirect_url(user):
    if user.is_superuser:
        return '/admin/'
    try:
        if user.is_manager():
            return 'manager_dashboard'
        elif user.is_cashier():
            return 'cashier_dashboard'
    except Exception:
        pass
    return 'login'
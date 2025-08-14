from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Business, User
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
                # Generate slug-safe business name for usernames
                base_name = re.sub(r'[^a-z0-9]+', '', form.cleaned_data['name'].lower().replace(' ', ''))
                
                with transaction.atomic():
                    # Create business
                    business = Business.objects.create(
                        name=form.cleaned_data['name'],
                        address=form.cleaned_data.get('address'),
                        phone_number=form.cleaned_data.get('phone_number'),
                        email=form.cleaned_data.get('email'),
                        website=form.cleaned_data.get('website')
                    )
                    
                    # Create manager user
                    manager_username = f"manager@{base_name}"
                    User.objects.create_user(
                        username=manager_username,
                        password=form.cleaned_data['password'],
                        role='manager',
                        business=business
                    )
                    
                    # Create cashier user
                    cashier_username = f"cashier@{base_name}"
                    User.objects.create_user(
                        username=cashier_username,
                        password=form.cleaned_data['password'],
                        role='cashier',
                        business=business
                    )
                    
                messages.success(request, f'Business "{business.name}" created with manager and cashier accounts.')
                return redirect('business_list')
                
            except IntegrityError as e:
                messages.error(request, f'Error creating business: {e}')
            except Exception as e:
                messages.error(request, f'Unexpected error: {e}')
    else:
        form = BusinessCreationForm()
    
    return render(request, 'accounts/create_business.html', {'form': form})

@login_required
@user_passes_test(is_superuser)
def business_list(request):
    businesses = Business.objects.all().prefetch_related('users')
    return render(request, 'accounts/business_list.html', {'businesses': businesses})

def login_view(request):
    if request.user.is_authenticated:
        return redirect(get_redirect_url(request.user))
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_superuser:
                messages.error(request, 'Superusers must use the admin login')
                return render(request, 'accounts/login.html')
                
            auth_login(request, user)
            return redirect(get_redirect_url(user))
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'accounts/login.html')

def get_redirect_url(user):
    if user.is_manager():
        return 'manager_dashboard'
    elif user.is_cashier():
        return 'cashier_dashboard'
    # Add a fallback for admin users
    return 'admin:index'

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')


def root_redirect(request):
    if request.user.is_authenticated:
        return redirect(get_redirect_url(request.user))
    else:
        return redirect('login')    
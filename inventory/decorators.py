from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied

def manager_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Redirect to login
            from django.shortcuts import redirect
            return redirect('login')
        
        if not request.user.is_manager():
            raise PermissionDenied("You don't have permission to access this page.")
        
        return view_func(request, *args, **kwargs)
    return wrapper

def cashier_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Redirect to login
            from django.shortcuts import redirect
            return redirect('login')
        
        if not request.user.is_cashier():
            raise PermissionDenied("You don't have permission to access this page.")
        
        return view_func(request, *args, **kwargs)
    return wrapper
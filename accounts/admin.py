from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Business, User

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'role', 'business', 'is_active')
    list_filter = ('role', 'business')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Permissions', {'fields': ('role', 'business', 'is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'business'),
        }),
    )
    search_fields = ('username', 'business__name')
    ordering = ('business__name', 'username')

admin.site.register(Business)
admin.site.register(User, CustomUserAdmin)
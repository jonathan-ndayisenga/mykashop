from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    manager_email = models.EmailField()  # Added for low stock alerts

    def __str__(self):
        return self.name


class CustomUserManager(BaseUserManager):
    def create_user(self, username, password, role, business, **extra_fields):
        if not username:
            raise ValueError('The Username must be set')
        if not password:
            raise ValueError('The Password must be set')
        if not role:
            raise ValueError('Role must be set')
        if not business:
            raise ValueError('Business must be set')

        user = self.model(
            username=username,
            role=role,
            business=business,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        # Superuser is always a manager
        extra_fields.setdefault('role', 'manager')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        # Create default business if not passed
        if 'business' not in extra_fields:
            default_business, _ = Business.objects.get_or_create(
                name="Admin Business",
                manager_email="admin@example.com"  # Default email
            )
            extra_fields['business'] = default_business

        return self.create_user(username, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = (
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='users'
    )

    # Remove unused fields from AbstractUser
    first_name = None
    last_name = None
    email = None

    objects = CustomUserManager()

    # Use username as the login field
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []  # No email required for superuser

    class Meta:
        unique_together = (('business', 'role'),)

    def clean(self):
        if self.role == 'manager':
            existing_manager = User.objects.filter(
                business=self.business,
                role='manager'
            ).exclude(pk=self.pk).first()
            if existing_manager:
                raise ValidationError(
                    _('A manager already exists for this business.')
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def is_manager(self):
        return self.role == 'manager'

    def is_cashier(self):
        return self.role == 'cashier'

    def __str__(self):
        return f"{self.username} ({self.business.name})"
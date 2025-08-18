from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from pydantic import ValidationError

from accounts.models import User, Business  # Import Business model

class Category(models.Model):
    name = models.CharField(max_length=100)
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['business', 'name'],
                name='unique_category_per_business'
            )
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
    # Prevent deletion if category has products
     if self.products.exists():  # use 'products', matching related_name
        raise ValidationError("Cannot delete category with associated products. Move products first.")
     super().delete(*args, **kwargs)
        
class Product(models.Model):
    UNIT_CHOICES = [
        ('pcs', 'Pieces'),
        ('kg', 'Kilograms'),
        ('ltr', 'Liters'),
        ('mtr', 'Meters'),
        ('tray', 'Trays'),
        ('box', 'Box'),
    ]
    
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    stock_quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')
    buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE)
    low_stock_threshold = models.PositiveIntegerField(default=5)  # Threshold field
    last_restocked = models.DateTimeField(null=True, blank=True)
    category = models.ForeignKey(
        Category, 
        on_delete=models.PROTECT,  # Prevent deletion if products exist
        related_name='products'
    )    

    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    def __str__(self):
        return self.name

@receiver(post_save, sender=Product)
def check_stock_level(sender, instance, **kwargs):
    if instance.is_low_stock():
        subject = f"Low Stock Alert: {instance.name}"
        message = (
            f"Product: {instance.name}\n"
            f"Current Stock: {instance.stock_quantity} {instance.get_unit_display()}\n"
            f"Threshold: {instance.low_stock_threshold}"
        )
        # Send to business's manager email
        if instance.business.manager_email:
            send_mail(
                subject,
                message,
                'inventory@system.com',
                [instance.business.manager_email],  # Use manager email
                fail_silently=True,
            )

class Sale(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    receipt_number = models.CharField(max_length=20, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            if not self.pk:
                super().save(*args, **kwargs)
                
            current_date = self.created_at.date()
            last_sale = Sale.objects.filter(
                business=self.business,
                created_at__date=current_date
            ).order_by('-receipt_number').first()
            
            if last_sale:
                try:
                    last_num = int(last_sale.receipt_number.split('-')[-1])
                    new_num = last_num + 1
                except (IndexError, ValueError):
                    new_num = 1
            else:
                new_num = 1
                
            self.receipt_number = f"REC-{current_date.strftime('%Y%m%d')}-{new_num:04d}"
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale #{self.receipt_number}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

class Restock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    restocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    restocked_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.product.stock_quantity += self.quantity
        self.product.last_restocked = timezone.now()
        self.product.save()
        super().save(*args, **kwargs)
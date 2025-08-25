from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db.models import Sum, F

from accounts.models import User, Business  # Business model


# -------------------------
# Category
# -------------------------
class Category(models.Model):
    name = models.CharField(max_length=100)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
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
        if self.products.exists():  # products comes from Product.related_name
            raise ValidationError("Cannot delete category with associated products. Move products first.")
        super().delete(*args, **kwargs)


# -------------------------
# Product
# -------------------------
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
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # prevent deleting category if products exist
        related_name='products'
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')
    buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    last_restocked = models.DateTimeField(null=True, blank=True)
    initial_stock = models.PositiveIntegerField(default=0)
    current_stock = models.PositiveIntegerField(default=0)
    
    def save(self, *args, **kwargs):
        # Set initial stock only when first creating the product
        if not self.pk:
            self.initial_stock = self.stock_quantity
            self.current_stock = self.stock_quantity
        super().save(*args, **kwargs)
    
    def update_stock(self, quantity_change):
        """Update current stock when items are sold or restocked"""
        self.current_stock += quantity_change
        if self.current_stock < 0:
            raise ValidationError("Insufficient stock")
        self.save()

    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    def __str__(self):
        return self.name
    def update_stock(self, quantity):
        """Update stock quantity and ensure it doesn't go negative"""
        self.stock_quantity += quantity
        if self.stock_quantity < 0:
            raise ValidationError("Insufficient stock")
        self.save()
    
    def get_total_sold(self):
        """Calculate total quantity sold"""
        return self.saleitem_set.aggregate(total=Sum('quantity'))['total'] or 0
    
    def get_total_revenue(self):
        """Calculate total revenue from sales"""
        return self.saleitem_set.aggregate(total=Sum(F('quantity') * F('unit_price')))['total'] or 0
    
    def get_profit(self):
        """Calculate total profit from sales"""
        revenue = self.get_total_revenue()
        cost = self.get_total_sold() * self.buying_price
        return revenue - cost

# Send low stock email alerts
@receiver(post_save, sender=Product)
def check_stock_level(sender, instance, **kwargs):
    if instance.is_low_stock():
        subject = f"Low Stock Alert: {instance.name}"
        message = (
            f"Product: {instance.name}\n"
            f"Current Stock: {instance.stock_quantity} {instance.get_unit_display()}\n"
            f"Threshold: {instance.low_stock_threshold}"
        )
        if instance.business.manager_email:
            send_mail(
                subject,
                message,
                'inventory@system.com',
                [instance.business.manager_email],
                fail_silently=True,
            )


# -------------------------
# Sale
# -------------------------
class Sale(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    receipt_number = models.CharField(max_length=20, unique=True, blank=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    customer_phone = models.CharField(max_length=15, blank=True, null=True)
    is_credit = models.BooleanField(default=False)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def save(self, *args, **kwargs):
        # Calculate balance for credit sales
        if self.is_credit:
            self.balance = self.total_amount - self.amount_paid
        else:
            self.amount_paid = self.total_amount
            self.balance = 0
        
        super().save(*args, **kwargs)
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


# -------------------------
# SaleItem
# -------------------------
class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='sale_items', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


# -------------------------
# Restock
# -------------------------
class Restock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    restocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    restocked_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    supplier = models.CharField(max_length=100, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        # Update product stock
        self.product.update_stock(self.quantity)
        self.product.last_restocked = timezone.now()
        self.product.save()
        super().save(*args, **kwargs)
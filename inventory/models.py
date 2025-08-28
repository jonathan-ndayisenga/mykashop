from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.db.models import Sum, F

from accounts.models import Business

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
        if self.product_set.exists():
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
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    stock_quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pcs')
    buying_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    last_restocked = models.DateTimeField(null=True, blank=True)
    initial_stock = models.PositiveIntegerField(default=0)
    
    def save(self, *args, **kwargs):
        if not self.pk:
            self.initial_stock = self.stock_quantity
        super().save(*args, **kwargs)
    
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    def __str__(self):
        return self.name
        
    def get_stock_value(self):
        return self.stock_quantity * self.buying_price
    
    def get_profit_margin(self):
        if self.buying_price == 0:
            return 0
        return ((self.selling_price - self.buying_price) / self.buying_price) * 100
        
    def log_stock_change(self, action, quantity_change, user, buying_price=None, selling_price=None, notes="", reference=""):
        previous_stock = self.stock_quantity
        self.stock_quantity += quantity_change
        
        if self.stock_quantity < 0:
            raise ValidationError("Insufficient stock")
        
        self.save()
        
        StockLog.objects.create(
            product=self,
            action=action,
            quantity_change=quantity_change,
            previous_stock=previous_stock,
            new_stock=self.stock_quantity,
            buying_price=buying_price if buying_price is not None else self.buying_price,
            selling_price=selling_price if selling_price is not None else self.selling_price,
            notes=notes,
            created_by=user,
            reference=reference
        )

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
        if not self.receipt_number:
            current_date = self.created_at.date() if self.created_at else timezone.now().date()
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
        
        if self.is_credit:
            self.balance = self.total_amount - self.amount_paid
        else:
            self.amount_paid = self.total_amount
            self.balance = 0

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale #{self.receipt_number}"

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

class StockLog(models.Model):
    ACTION_CHOICES = (
        ('restock', 'Restock'),
        ('sale', 'Sale'),
        ('adjustment', 'Adjustment'),
        ('initial', 'Initial Stock'),
    )
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity_change = models.IntegerField()
    previous_stock = models.IntegerField()
    new_stock = models.IntegerField()
    buying_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product.name} - {self.action} - {self.quantity_change}"
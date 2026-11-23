"""
Inventory Management Models
============================
Core models for stock tracking, warehouse management, and inventory operations.
"""
from django.db import models
from django.core.validators import MinValueValidator


class Warehouse(models.Model):
    """Represents a warehouse or storage location."""
    
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Warehouses'

    def __str__(self):
        return f"{self.code} - {self.name}"


class Category(models.Model):
    """Product categories for inventory classification."""
    
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Main product model for inventory items."""
    
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products'
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0
    )
    reorder_level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property
    def total_stock(self):
        """Calculate total stock across all warehouses."""
        return sum(stock.quantity for stock in self.stock_levels.all())


class StockLevel(models.Model):
    """Tracks stock levels per product per warehouse."""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_levels'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='stock_levels'
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    last_counted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['product', 'warehouse']
        ordering = ['warehouse', 'product']

    def __str__(self):
        return f"{self.product.sku} @ {self.warehouse.code}: {self.quantity}"

    @property
    def available_quantity(self):
        """Calculate available quantity (total - reserved)."""
        return self.quantity - self.reserved_quantity


class StockMovement(models.Model):
    """Tracks all stock movements (in/out/transfer)."""
    
    MOVEMENT_TYPES = [
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('TRANSFER_IN', 'Transfer In'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('ADJUSTMENT', 'Adjustment'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()  # Can be negative for out
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    performed_by = models.CharField(max_length=100)  # User ID or name
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['warehouse', '-created_at']),
        ]

    def __str__(self):
        return f"{self.movement_type}: {self.product.sku} ({self.quantity})"

    def save(self, *args, **kwargs):
        """Update stock level when movement is created."""
        super().save(*args, **kwargs)
        
        stock_level, created = StockLevel.objects.get_or_create(
            product=self.product,
            warehouse=self.warehouse,
            defaults={'quantity': 0}
        )
        
        if self.movement_type in ['IN', 'TRANSFER_IN']:
            stock_level.quantity += abs(self.quantity)
        elif self.movement_type in ['OUT', 'TRANSFER_OUT']:
            stock_level.quantity -= abs(self.quantity)
        elif self.movement_type == 'ADJUSTMENT':
            stock_level.quantity = self.quantity
        
        stock_level.save()

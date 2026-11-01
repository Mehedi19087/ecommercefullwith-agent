from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def clean(self):
        super().clean()
        if self.parent_id and self.id and self.parent_id == self.id:
            raise DjangoValidationError("A category cannot be its own parent.")
        curr = self.parent
        while curr is not None:
            if curr.id == self.id:
                raise DjangoValidationError("Category cycles are not allowed.")
            curr = curr.parent

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    sku = models.CharField(max_length=64, unique=True)
    options = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} ({self.sku})"


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images',
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='images',
    )
    image_url = models.URLField(max_length=500, default='')
    alt_text = models.CharField(max_length=200, blank=True, default='')
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']

    def clean(self):
        super().clean()
        if self.variant_id and self.variant.product_id != self.product_id:
            raise DjangoValidationError("The assigned variant must belong to the same product.")

    def __str__(self):
        return f"Image for {self.product.name}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        RECEIVED = 'received', 'Received'
        SALE = 'sale', 'Sale'
        CANCELLATION = 'cancellation', 'Cancellation'
        RETURN = 'return', 'Return'
        DAMAGE = 'damage', 'Damage'
        CORRECTION = 'correction', 'Correction'

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name='stock_movements',
    )
    order_item = models.ForeignKey(
        'orders.OrderItem',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_movements',
    )
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.variant.sku} ({self.quantity_change}) - {self.reason}"

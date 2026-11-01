import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        RETURNED = 'returned', 'Returned'

    number = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout_key = models.UUIDField(unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
    guest_access_token_hash = models.CharField(max_length=64, null=True, blank=True, unique=True)
    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField(blank=True, default='')
    customer_phone = models.CharField(max_length=20)
    delivery_address_line = models.TextField()
    delivery_area = models.CharField(max_length=100, blank=True, default='')
    delivery_city = models.CharField(max_length=100)
    delivery_postal_code = models.CharField(max_length=20, blank=True, default='')
    delivery_country_code = models.CharField(max_length=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    currency = models.CharField(max_length=3, default='USD')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    customer_note = models.TextField(blank=True, default='')
    courier_name = models.CharField(max_length=100, blank=True, default='')
    tracking_number = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.number} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='items',
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=64)
    variant_options = models.JSONField(default=dict, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    returned_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['order', 'variant'], name='unique_order_variant'),
            CheckConstraint(condition=Q(quantity__gt=0), name='order_item_quantity_gt_zero'),
            CheckConstraint(condition=Q(returned_quantity__lte=F('quantity')), name='order_item_returned_lte_quantity'),
        ]
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.product_name} ({self.sku})"


class Payment(models.Model):
    class Method(models.TextChoices):
        COD = 'cod', 'Cash on Delivery'
        MANUAL = 'manual', 'Manual'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    method = models.CharField(max_length=20, choices=Method.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    reference = models.CharField(max_length=150, blank=True, default='')
    note = models.TextField(blank=True, default='')
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reference = models.CharField(max_length=150, blank=True, default='')
    refund_note = models.TextField(blank=True, default='')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_payments',
    )
    refunded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_refunds',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=['order'],
                condition=Q(status__in=['pending', 'succeeded']),
                name='unique_pending_or_succeeded_payment',
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} for Order {self.order.number} ({self.status})"

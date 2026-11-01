from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart',
    )
    guest_token_hash = models.CharField(max_length=64, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            CheckConstraint(
                condition=(
                    Q(user__isnull=False, guest_token_hash__isnull=True)
                    | Q(user__isnull=True, guest_token_hash__isnull=False)
                ),
                name='cart_user_xor_guest_token',
            )
        ]

    def __str__(self):
        if self.user:
            return f"Cart for user {self.user.username}"
        return f"Guest Cart ({self.guest_token_hash[:8]}...)"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    variant = models.ForeignKey(
        'catalog.ProductVariant',
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['cart', 'variant'], name='unique_cart_variant'),
            CheckConstraint(condition=Q(quantity__gt=0), name='cart_item_quantity_gt_zero'),
        ]
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.variant.sku} in Cart {self.cart_id}"

import logging
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, ValidationError

from catalog.models import ProductVariant
from .models import Cart, CartItem

logger = logging.getLogger(__name__)


def add_item_to_cart(cart: Cart, validated_data: dict) -> CartItem:
    variant_id = validated_data['variant_id']
    quantity = validated_data['quantity']

    try:
        variant = ProductVariant.objects.select_related('product__category').get(id=variant_id)
    except ProductVariant.DoesNotExist:
        raise ValidationError({"variant_id": "Product variant does not exist."})

    if not (variant.is_active and variant.product.is_active and variant.product.category.is_active):
        raise ValidationError({"variant_id": "This product variant is currently unavailable."})

    with transaction.atomic():
        cart_item = CartItem.objects.filter(cart=cart, variant=variant).first()
        current_qty = cart_item.quantity if cart_item else 0
        total_requested = current_qty + quantity

        if total_requested > variant.stock_quantity:
            raise ValidationError(
                {
                    "quantity": f"Cannot add {quantity} items. Available stock is {variant.stock_quantity} (already {current_qty} in cart)."
                }
            )

        if cart_item:
            cart_item.quantity = total_requested
            cart_item.save(update_fields=['quantity', 'updated_at'])
            return cart_item

        return CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)


def update_cart_item(cart: Cart, item_id: int, validated_data: dict) -> CartItem:
    new_quantity = validated_data['quantity']

    try:
        cart_item = CartItem.objects.select_related('variant__product__category').get(id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        raise NotFound("Cart item not found.")

    variant = cart_item.variant
    if not (variant.is_active and variant.product.is_active and variant.product.category.is_active):
        raise ValidationError({"detail": "This product variant is currently unavailable."})

    if new_quantity > variant.stock_quantity:
        raise ValidationError(
            {"quantity": f"Cannot set quantity to {new_quantity}. Available stock is {variant.stock_quantity}."}
        )

    cart_item.quantity = new_quantity
    cart_item.save(update_fields=['quantity', 'updated_at'])
    return cart_item


def delete_cart_item(cart: Cart, item_id: int) -> None:
    try:
        cart_item = CartItem.objects.get(id=item_id, cart=cart)
    except CartItem.DoesNotExist:
        raise NotFound("Cart item not found.")
    cart_item.delete()


def clear_cart(cart: Cart) -> None:
    cart.items.all().delete()

import logging
import secrets
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from catalog.models import ProductVariant, StockMovement
from cart.models import CartItem
from cart.utils import get_or_create_cart
from users.models import Address
from .models import Order, OrderItem, Payment
from .utils import hash_token, is_order_owner

logger = logging.getLogger(__name__)


def checkout(request, validated_data: dict) -> tuple[Order, str | None, bool]:
    checkout_key = validated_data['checkout_key']

    # Retry idempotency check
    existing_order = Order.objects.filter(checkout_key=checkout_key).first()
    if existing_order:
        if is_order_owner(existing_order, request):
            return existing_order, None, False
        raise ValidationError({"checkout_key": "Checkout key is already in use by another customer."})

    cart, _ = get_or_create_cart(request)

    with transaction.atomic():
        cart_items = list(
            CartItem.objects.select_for_update().filter(cart=cart).select_related('variant__product')
        )
        if not cart_items:
            raise ValidationError({"detail": "Cannot checkout an empty cart."})

        variant_ids = [ci.variant_id for ci in cart_items]
        variants = {
            v.id: v
            for v in ProductVariant.objects.select_for_update()
            .filter(id__in=variant_ids)
            .select_related('product__category')
        }

        # Validate availability and stock
        for ci in cart_items:
            variant = variants.get(ci.variant_id)
            if not variant or not (variant.is_active and variant.product.is_active and variant.product.category.is_active):
                prod_name = variant.product.name if variant else "Item"
                raise ValidationError({"detail": f"Product '{prod_name}' is currently unavailable."})
            if variant.stock_quantity < ci.quantity:
                raise ValidationError(
                    {
                        "detail": f"Insufficient stock for '{variant.product.name}' ({variant.sku}). Available: {variant.stock_quantity}."
                    }
                )

        # Resolve recipient and delivery address
        user = request.user if request.user.is_authenticated else None
        address_id = validated_data.get('address_id')

        if user and address_id:
            try:
                addr = Address.objects.get(id=address_id, user=user)
            except Address.DoesNotExist:
                raise ValidationError({"address_id": "Saved address not found."})

            recipient_name = addr.recipient_name
            phone = addr.phone
            address_line = addr.address_line
            area = addr.area
            city = addr.city
            postal_code = addr.postal_code
            country_code = addr.country_code
        else:
            if not validated_data.get('recipient_name') and validated_data.get('customer_name'):
                validated_data['recipient_name'] = validated_data['customer_name']
            if not validated_data.get('phone') and validated_data.get('customer_phone'):
                validated_data['phone'] = validated_data['customer_phone']

            required_delivery = [
                'recipient_name',
                'phone',
                'delivery_address_line',
                'delivery_city',
                'delivery_country_code',
            ]
            for field in required_delivery:
                if not validated_data.get(field):
                    raise ValidationError({field: f"{field.replace('_', ' ').capitalize()} is required."})

            recipient_name = validated_data['recipient_name'].strip()
            phone = validated_data['phone'].strip()
            address_line = validated_data['delivery_address_line'].strip()
            area = validated_data.get('delivery_area', '').strip()
            city = validated_data['delivery_city'].strip()
            postal_code = validated_data.get('delivery_postal_code', '').strip()
            country_code = validated_data['delivery_country_code'].strip()

        customer_name = (
            validated_data.get('customer_name', '').strip()
            or recipient_name
            or (user.get_full_name() if user else '')
        )
        customer_email = (
            validated_data.get('customer_email', '').strip()
            or (user.email if user else '')
        )
        customer_phone = (
            validated_data.get('customer_phone', '').strip()
            or phone
            or (user.mobile_number if user else '')
        )

        subtotal = sum(ci.quantity * variants[ci.variant_id].price for ci in cart_items)
        delivery_fee = Decimal('0.00')
        tax_total = Decimal('0.00')
        total = subtotal + delivery_fee + tax_total

        raw_order_token = None
        guest_access_token_hash = None
        if not user:
            raw_order_token = secrets.token_urlsafe(32)
            guest_access_token_hash = hash_token(raw_order_token)

        order = Order.objects.create(
            checkout_key=checkout_key,
            user=user,
            guest_access_token_hash=guest_access_token_hash,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            delivery_address_line=address_line,
            delivery_area=area,
            delivery_city=city,
            delivery_postal_code=postal_code,
            delivery_country_code=country_code,
            status=Order.Status.PENDING,
            currency='USD',
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            tax_total=tax_total,
            total=total,
            customer_note=validated_data.get('customer_note', '').strip(),
        )

        for ci in cart_items:
            variant = variants[ci.variant_id]
            order_item = OrderItem.objects.create(
                order=order,
                variant=variant,
                product_name=variant.product.name,
                sku=variant.sku,
                variant_options=variant.options,
                unit_price=variant.price,
                quantity=ci.quantity,
                line_total=variant.price * ci.quantity,
                returned_quantity=0,
            )

            # Deduct stock and record movement
            variant.stock_quantity -= ci.quantity
            variant.save(update_fields=['stock_quantity', 'updated_at'])

            StockMovement.objects.create(
                variant=variant,
                order_item=order_item,
                quantity_change=-ci.quantity,
                reason=StockMovement.Reason.SALE,
                created_by=user,
            )

        Payment.objects.create(
            order=order,
            method=validated_data.get('payment_method', Payment.Method.COD),
            status=Payment.Status.PENDING,
            amount=total,
            currency='USD',
        )

        # Clear cart items atomically
        cart.items.all().delete()

        return order, raw_order_token, True


def cancel_order(order: Order, user=None) -> Order:
    if order.status not in [Order.Status.PENDING, Order.Status.CONFIRMED]:
        raise ValidationError({"detail": f"Cannot cancel order with status '{order.status}'."})

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)
        items = list(locked_order.items.select_for_update().select_related('variant'))
        variant_ids = [item.variant_id for item in items]
        variants = {
            v.id: v
            for v in ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
        }

        for item in items:
            variant = variants[item.variant_id]
            variant.stock_quantity += item.quantity
            variant.save(update_fields=['stock_quantity', 'updated_at'])

            StockMovement.objects.create(
                variant=variant,
                order_item=item,
                quantity_change=item.quantity,
                reason=StockMovement.Reason.CANCELLATION,
                created_by=user if user and user.is_authenticated else None,
            )

        # Mark pending payment cancelled
        locked_order.payments.filter(status=Payment.Status.PENDING).update(status=Payment.Status.CANCELLED)

        locked_order.status = Order.Status.CANCELLED
        locked_order.save(update_fields=['status', 'updated_at'])
        return locked_order


def update_staff_order(order: Order, validated_data: dict) -> Order:
    allowed_transitions = {
        Order.Status.PENDING: [Order.Status.CONFIRMED],
        Order.Status.CONFIRMED: [Order.Status.SHIPPED],
        Order.Status.SHIPPED: [Order.Status.DELIVERED],
    }

    new_status = validated_data.get('status')
    if new_status:
        valid_next = allowed_transitions.get(order.status, [])
        if new_status not in valid_next:
            raise ValidationError(
                {"status": f"Cannot transition order status from '{order.status}' to '{new_status}'."}
            )
        order.status = new_status

    if 'courier_name' in validated_data:
        order.courier_name = validated_data['courier_name'].strip()
    if 'tracking_number' in validated_data:
        order.tracking_number = validated_data['tracking_number'].strip()

    order.save()
    return order


def process_order_return(order: Order, validated_data: dict, staff_user=None) -> Order:
    if order.status != Order.Status.DELIVERED:
        raise ValidationError({"detail": f"Cannot process returns for an order with status '{order.status}'. Order must be delivered."})

    item_id = validated_data['item_id']
    quantity = validated_data['quantity']
    restock_quantity = validated_data['restock_quantity']
    note = validated_data.get('note', '').strip()

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)
        try:
            item = OrderItem.objects.select_for_update().select_related('variant').get(id=item_id, order=locked_order)
        except OrderItem.DoesNotExist:
            raise ValidationError({"item_id": "Order item does not belong to this order."})

        remaining_returnable = item.quantity - item.returned_quantity
        if quantity > remaining_returnable:
            raise ValidationError(
                {"quantity": f"Cannot return {quantity} items. Only {remaining_returnable} units remain returnable."}
            )

        item.returned_quantity += quantity
        item.save(update_fields=['returned_quantity'])

        if restock_quantity > 0:
            variant = ProductVariant.objects.select_for_update().get(id=item.variant_id)
            variant.stock_quantity += restock_quantity
            variant.save(update_fields=['stock_quantity', 'updated_at'])

            StockMovement.objects.create(
                variant=variant,
                order_item=item,
                quantity_change=restock_quantity,
                reason=StockMovement.Reason.RETURN,
                note=note,
                created_by=staff_user,
            )

        # Check if all items in order have been fully returned
        all_items = locked_order.items.all()
        if all(i.returned_quantity == i.quantity for i in all_items):
            locked_order.status = Order.Status.RETURNED
            locked_order.save(update_fields=['status', 'updated_at'])

        return locked_order


def record_staff_payment(order: Order, validated_data: dict, staff_user=None) -> Payment:
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(id=order.id)

        if locked_order.status in [Order.Status.CANCELLED, Order.Status.RETURNED]:
            raise ValidationError({"detail": f"Cannot record payment for an order with status '{locked_order.status}'."})

        if locked_order.payments.filter(status=Payment.Status.REFUNDED).exists():
            raise ValidationError({"detail": "Cannot record payment for an order that already has a refunded payment."})

        payment_id = validated_data.get('payment_id')
        new_status = validated_data['status']
        ref = validated_data.get('reference', '').strip()
        note = validated_data.get('note', '').strip()

        if payment_id:
            try:
                payment = Payment.objects.select_for_update().get(id=payment_id, order=locked_order)
            except Payment.DoesNotExist:
                raise ValidationError({"payment_id": "Payment not found for this order."})

            if payment.status != Payment.Status.PENDING:
                raise ValidationError({"detail": f"Only pending payments can be updated. Current status is '{payment.status}'."})

            payment.status = new_status
            if ref:
                payment.reference = ref
            if note:
                payment.note = note
            if new_status == Payment.Status.SUCCEEDED:
                payment.paid_at = timezone.now()
            payment.recorded_by = staff_user
            payment.save()
            return payment

        # Creating a retry attempt
        if locked_order.payments.filter(status__in=[Payment.Status.PENDING, Payment.Status.SUCCEEDED]).exists():
            raise ValidationError({"detail": "Order already has an active pending or succeeded payment attempt."})

        method = validated_data.get('method')
        if not method:
            raise ValidationError({"method": "Payment method is required when creating a retry attempt."})

        payment = Payment.objects.create(
            order=locked_order,
            method=method,
            status=new_status,
            amount=locked_order.total,
            currency=locked_order.currency,
            reference=ref,
            note=note,
            paid_at=timezone.now() if new_status == Payment.Status.SUCCEEDED else None,
            recorded_by=staff_user,
        )
        return payment


def process_staff_refund(payment_id: int, validated_data: dict, staff_user=None) -> Payment:
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().select_related('order').get(id=payment_id)
        except Payment.DoesNotExist:
            raise NotFound("Payment not found.")

        # Idempotent repeated request
        if payment.status == Payment.Status.REFUNDED:
            return payment

        if payment.order.status not in [Order.Status.CANCELLED, Order.Status.RETURNED]:
            raise ValidationError(
                {"detail": f"Cannot refund payment for order in status '{payment.order.status}'. Order must be cancelled or returned."}
            )

        if payment.status != Payment.Status.SUCCEEDED:
            raise ValidationError(
                {"detail": f"Cannot refund payment in status '{payment.status}'. Only succeeded payments can be refunded."}
            )

        payment.status = Payment.Status.REFUNDED
        payment.refunded_at = timezone.now()
        payment.refund_reference = validated_data.get('refund_reference', '').strip()
        payment.refund_note = validated_data.get('refund_note', '').strip()
        payment.refunded_by = staff_user
        payment.save()
        return payment

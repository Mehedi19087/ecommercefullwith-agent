from decimal import Decimal
from rest_framework import serializers

from .models import Order, OrderItem, Payment


class CheckoutRequestSerializer(serializers.Serializer):
    checkout_key = serializers.UUIDField()
    address_id = serializers.IntegerField(required=False, allow_null=True)
    recipient_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    delivery_address_line = serializers.CharField(required=False)
    delivery_area = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    delivery_city = serializers.CharField(max_length=100, required=False)
    delivery_postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    delivery_country_code = serializers.CharField(max_length=2, required=False)
    customer_name = serializers.CharField(max_length=150, required=False)
    customer_email = serializers.EmailField(required=False, allow_blank=True, default='')
    customer_phone = serializers.CharField(max_length=20, required=False)
    payment_method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.COD,
    )
    customer_note = serializers.CharField(required=False, allow_blank=True, default='')


class OrderItemResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    sku = serializers.CharField(read_only=True)
    variant_options = serializers.DictField(read_only=True)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    returned_quantity = serializers.IntegerField(read_only=True)


class PaymentResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True)
    method = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    currency = serializers.CharField(read_only=True)
    reference = serializers.CharField(read_only=True)
    note = serializers.CharField(read_only=True)
    paid_at = serializers.DateTimeField(read_only=True, allow_null=True)
    refunded_at = serializers.DateTimeField(read_only=True, allow_null=True)
    refund_reference = serializers.CharField(read_only=True)
    refund_note = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class OrderSummaryResponseSerializer(serializers.Serializer):
    number = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    currency = serializers.CharField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    delivery_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    tax_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    items_count = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    def get_items_count(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_payment_status(self, obj):
        payments = list(obj.payments.all())
        if any(p.status == Payment.Status.REFUNDED for p in payments):
            return Payment.Status.REFUNDED
        if any(p.status == Payment.Status.SUCCEEDED for p in payments):
            return Payment.Status.SUCCEEDED
        if any(p.status == Payment.Status.PENDING for p in payments):
            return Payment.Status.PENDING
        if payments:
            return payments[0].status
        return Payment.Status.PENDING


class OrderDetailResponseSerializer(serializers.Serializer):
    number = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    currency = serializers.CharField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    delivery_fee = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    tax_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    customer_name = serializers.CharField(read_only=True)
    customer_email = serializers.EmailField(read_only=True)
    customer_phone = serializers.CharField(read_only=True)
    delivery_address_line = serializers.CharField(read_only=True)
    delivery_area = serializers.CharField(read_only=True)
    delivery_city = serializers.CharField(read_only=True)
    delivery_postal_code = serializers.CharField(read_only=True)
    delivery_country_code = serializers.CharField(read_only=True)
    customer_note = serializers.CharField(read_only=True)
    courier_name = serializers.CharField(read_only=True)
    tracking_number = serializers.CharField(read_only=True)
    payment_status = serializers.SerializerMethodField()
    items = OrderItemResponseSerializer(many=True, read_only=True)
    payments = PaymentResponseSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_payment_status(self, obj):
        payments = list(obj.payments.all())
        if any(p.status == Payment.Status.REFUNDED for p in payments):
            return Payment.Status.REFUNDED
        if any(p.status == Payment.Status.SUCCEEDED for p in payments):
            return Payment.Status.SUCCEEDED
        if any(p.status == Payment.Status.PENDING for p in payments):
            return Payment.Status.PENDING
        if payments:
            return payments[0].status
        return Payment.Status.PENDING


class StaffOrderUpdateRequestSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            Order.Status.CONFIRMED,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        ],
        required=False,
    )
    courier_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tracking_number = serializers.CharField(max_length=100, required=False, allow_blank=True)


class OrderReturnRequestSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    restock_quantity = serializers.IntegerField(min_value=0)
    note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs['restock_quantity'] > attrs['quantity']:
            raise serializers.ValidationError({"restock_quantity": "Restock quantity cannot exceed returned quantity."})
        return attrs


class StaffPaymentRequestSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(required=False, allow_null=True)
    method = serializers.ChoiceField(choices=Payment.Method.choices, required=False)
    status = serializers.ChoiceField(
        choices=[
            Payment.Status.SUCCEEDED,
            Payment.Status.FAILED,
            Payment.Status.CANCELLED,
        ]
    )
    reference = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    note = serializers.CharField(required=False, allow_blank=True, default='')


class StaffRefundRequestSerializer(serializers.Serializer):
    refund_reference = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    refund_note = serializers.CharField(required=False, allow_blank=True, default='')

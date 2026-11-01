from django.contrib import admin
from .models import Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product_name', 'sku', 'variant_options', 'unit_price', 'quantity', 'line_total', 'returned_quantity']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['method', 'status', 'amount', 'currency', 'reference', 'paid_at', 'refunded_at', 'recorded_by', 'refunded_by', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'customer_name', 'customer_phone', 'status', 'total', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['number', 'customer_name', 'customer_phone', 'customer_email']
    readonly_fields = ['number', 'checkout_key', 'created_at', 'updated_at']
    inlines = [OrderItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'method', 'status', 'amount', 'currency', 'paid_at', 'refunded_at']
    list_filter = ['method', 'status', 'created_at']
    search_fields = ['order__number', 'reference', 'refund_reference']

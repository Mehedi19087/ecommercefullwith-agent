from decimal import Decimal
from rest_framework import serializers


class AddToCartRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class UpdateCartItemRequestSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class CartItemResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    variant_id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(source='variant.product.id', read_only=True)
    product_name = serializers.CharField(source='variant.product.name', read_only=True)
    sku = serializers.CharField(source='variant.sku', read_only=True)
    options = serializers.DictField(source='variant.options', read_only=True)
    unit_price = serializers.DecimalField(source='variant.price', max_digits=12, decimal_places=2, read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    line_total = serializers.SerializerMethodField()
    available_stock = serializers.IntegerField(source='variant.stock_quantity', read_only=True)

    def get_line_total(self, obj):
        return obj.variant.price * obj.quantity


class CartResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    items = CartItemResponseSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

    def get_subtotal(self, obj):
        return sum(item.variant.price * item.quantity for item in obj.items.all())

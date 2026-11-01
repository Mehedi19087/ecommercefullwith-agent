from decimal import Decimal
from rest_framework import serializers

from .models import Category, Product, ProductImage, ProductVariant, StockMovement


class CategoryRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    slug = serializers.SlugField(max_length=120)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False, default=True)


class CategoryUpdateRequestSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    slug = serializers.SlugField(max_length=120, required=False)
    parent_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class CategoryResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    parent_id = serializers.IntegerField(read_only=True, allow_null=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class CreateVariantRequestSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64)
    options = serializers.DictField(child=serializers.CharField(), required=False, default=dict)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'))


class UpdateVariantRequestSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64, required=False)
    options = serializers.DictField(child=serializers.CharField(), required=False)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'), required=False)
    is_active = serializers.BooleanField(required=False)


class VariantResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    sku = serializers.CharField(read_only=True)
    options = serializers.DictField(read_only=True)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    stock_quantity = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ProductImageRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False)
    image_url = serializers.URLField(required=False)
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    alt_text = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    position = serializers.IntegerField(required=False, default=0, min_value=0)

    def validate(self, attrs):
        if not attrs.get('image') and not attrs.get('image_url'):
            raise serializers.ValidationError("Either an image file or an image_url must be provided.")
        return attrs


class ProductImageUpdateRequestSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False)
    image_url = serializers.URLField(required=False)
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    alt_text = serializers.CharField(max_length=200, required=False, allow_blank=True)
    position = serializers.IntegerField(required=False, min_value=0)


class ProductImageResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)
    variant_id = serializers.IntegerField(read_only=True, allow_null=True)
    image_url = serializers.URLField(read_only=True)
    alt_text = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class CreateProductRequestSerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    name = serializers.CharField(max_length=200)
    slug = serializers.SlugField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    is_active = serializers.BooleanField(required=False, default=False)
    initial_variant = CreateVariantRequestSerializer()


class UpdateProductRequestSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=200, required=False)
    slug = serializers.SlugField(max_length=220, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class ProductListResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    category_id = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    min_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    max_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    main_image_url = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class ProductDetailResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    category = CategoryResponseSerializer(read_only=True)
    variants = VariantResponseSerializer(many=True, read_only=True)
    images = ProductImageResponseSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class StockMovementRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    quantity_change = serializers.IntegerField()
    reason = serializers.ChoiceField(
        choices=[
            StockMovement.Reason.RECEIVED,
            StockMovement.Reason.DAMAGE,
            StockMovement.Reason.CORRECTION,
        ]
    )
    note = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        qty = attrs.get('quantity_change')
        reason = attrs.get('reason')
        note = attrs.get('note', '').strip()

        if qty == 0:
            raise serializers.ValidationError({"quantity_change": "Quantity change cannot be zero."})
        if reason == StockMovement.Reason.RECEIVED and qty <= 0:
            raise serializers.ValidationError({"quantity_change": "Received stock movement must be positive."})
        if reason == StockMovement.Reason.DAMAGE and qty >= 0:
            raise serializers.ValidationError({"quantity_change": "Damage stock movement must be negative."})
        if reason == StockMovement.Reason.CORRECTION and not note:
            raise serializers.ValidationError({"note": "A note is required for manual stock corrections."})
        return attrs


class StockMovementResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    variant_id = serializers.IntegerField(read_only=True)
    variant_sku = serializers.CharField(read_only=True)
    order_item_id = serializers.IntegerField(read_only=True, allow_null=True)
    quantity_change = serializers.IntegerField(read_only=True)
    reason = serializers.CharField(read_only=True)
    note = serializers.CharField(read_only=True)
    created_by_username = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)

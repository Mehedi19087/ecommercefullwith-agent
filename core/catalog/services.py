import logging
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, ValidationError

from .cloudinary_service import upload_image_to_cloudinary
from .models import Category, Product, ProductImage, ProductVariant, StockMovement

logger = logging.getLogger(__name__)


def create_category(validated_data: dict) -> Category:
    parent_id = validated_data.get('parent_id')
    parent = None
    if parent_id:
        try:
            parent = Category.objects.get(id=parent_id)
        except Category.DoesNotExist:
            raise ValidationError({"parent_id": "Parent category does not exist."})

    try:
        category = Category(
            name=validated_data['name'].strip(),
            slug=validated_data['slug'].strip(),
            parent=parent,
            is_active=validated_data.get('is_active', True),
        )
        category.full_clean()
        category.save()
        return category
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else str(exc))
    except IntegrityError as exc:
        logger.warning("Category creation failed: %s", exc)
        raise ValidationError({"non_field_errors": ["A category with this name or slug already exists."]})


def update_category(category: Category, validated_data: dict) -> Category:
    if 'name' in validated_data:
        category.name = validated_data['name'].strip()
    if 'slug' in validated_data:
        category.slug = validated_data['slug'].strip()
    if 'is_active' in validated_data:
        category.is_active = validated_data['is_active']
    if 'parent_id' in validated_data:
        parent_id = validated_data['parent_id']
        if parent_id is None:
            category.parent = None
        else:
            try:
                category.parent = Category.objects.get(id=parent_id)
            except Category.DoesNotExist:
                raise ValidationError({"parent_id": "Parent category does not exist."})

    try:
        category.full_clean()
        category.save()
        return category
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else str(exc))
    except IntegrityError as exc:
        logger.warning("Category update failed: %s", exc)
        raise ValidationError({"non_field_errors": ["A category with this name or slug already exists."]})


def delete_category(category: Category) -> None:
    if category.products.exists():
        raise ValidationError({"detail": "Cannot delete category that contains products."})
    if category.children.exists():
        raise ValidationError({"detail": "Cannot delete category that has child categories."})
    category.delete()


def _normalize_options(options: dict) -> dict:
    if not isinstance(options, dict):
        raise ValidationError({"options": "Options must be a key-value dictionary."})
    normalized = {}
    for k, v in options.items():
        key_str = str(k).strip()
        val_str = str(v).strip()
        if not key_str or not val_str:
            raise ValidationError({"options": "Option names and values cannot be empty."})
        normalized[key_str] = val_str
    return normalized


def create_product(validated_data: dict) -> Product:
    category_id = validated_data['category_id']
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        raise ValidationError({"category_id": "Category does not exist."})

    initial_variant_data = validated_data['initial_variant']
    options = _normalize_options(initial_variant_data.get('options', {}))

    with transaction.atomic():
        try:
            product = Product.objects.create(
                category=category,
                name=validated_data['name'].strip(),
                slug=validated_data['slug'].strip(),
                description=validated_data.get('description', '').strip(),
                is_active=False,  # default False until explicitly activated
            )
        except IntegrityError as exc:
            logger.warning("Product creation failed: %s", exc)
            raise ValidationError({"slug": "A product with this slug already exists."})

        try:
            ProductVariant.objects.create(
                product=product,
                sku=initial_variant_data['sku'].strip(),
                options=options,
                price=initial_variant_data['price'],
                stock_quantity=0,
                is_active=True,
            )
        except IntegrityError as exc:
            logger.warning("Initial variant creation failed: %s", exc)
            raise ValidationError({"initial_variant": {"sku": "A variant with this SKU already exists."}})

        # If user explicitly requested is_active=True, check rules before activating
        if validated_data.get('is_active', False):
            if not category.is_active:
                raise ValidationError({"is_active": "Cannot activate product in an inactive category."})
            product.is_active = True
            product.save(update_fields=['is_active'])

        return product


def update_product(product: Product, validated_data: dict) -> Product:
    if 'category_id' in validated_data:
        try:
            product.category = Category.objects.get(id=validated_data['category_id'])
        except Category.DoesNotExist:
            raise ValidationError({"category_id": "Category does not exist."})

    if 'name' in validated_data:
        product.name = validated_data['name'].strip()
    if 'slug' in validated_data:
        product.slug = validated_data['slug'].strip()
    if 'description' in validated_data:
        product.description = validated_data['description'].strip()

    if 'is_active' in validated_data:
        new_active = validated_data['is_active']
        if new_active:
            if not product.category.is_active:
                raise ValidationError({"is_active": "Cannot activate product whose category is inactive."})
            if not product.variants.filter(is_active=True).exists():
                raise ValidationError({"is_active": "Cannot activate product without an active variant."})
        product.is_active = new_active

    try:
        product.save()
        return product
    except IntegrityError as exc:
        logger.warning("Product update failed: %s", exc)
        raise ValidationError({"slug": "A product with this slug already exists."})


def delete_product(product: Product) -> None:
    from orders.models import OrderItem

    has_order_history = OrderItem.objects.filter(variant__product=product).exists()
    has_stock_history = StockMovement.objects.filter(variant__product=product).exists()

    if has_order_history or has_stock_history:
        raise ValidationError(
            {"detail": "Cannot delete product with order or stock history. Archive it by setting is_active=False."}
        )
    product.delete()


def create_variant(product: Product, validated_data: dict) -> ProductVariant:
    sku = validated_data['sku'].strip()
    options = _normalize_options(validated_data.get('options', {}))
    price = validated_data['price']

    with transaction.atomic():
        locked_product = Product.objects.select_for_update().get(id=product.id)
        existing_variants = locked_product.variants.all()

        for ev in existing_variants:
            if ev.options == options:
                raise ValidationError({"options": "A variant with this option combination already exists."})

        try:
            variant = ProductVariant.objects.create(
                product=locked_product,
                sku=sku,
                options=options,
                price=price,
                stock_quantity=0,
                is_active=True,
            )
            return variant
        except IntegrityError as exc:
            logger.warning("Variant creation failed: %s", exc)
            raise ValidationError({"sku": "A variant with this SKU already exists."})


def update_variant(variant: ProductVariant, validated_data: dict) -> ProductVariant:
    with transaction.atomic():
        locked_product = Product.objects.select_for_update().get(id=variant.product_id)
        variant = ProductVariant.objects.select_for_update().get(id=variant.id)

        if 'options' in validated_data:
            new_options = _normalize_options(validated_data['options'])
            for ev in locked_product.variants.exclude(id=variant.id):
                if ev.options == new_options:
                    raise ValidationError({"options": "A variant with this option combination already exists."})
            variant.options = new_options

        if 'sku' in validated_data:
            variant.sku = validated_data['sku'].strip()
        if 'price' in validated_data:
            variant.price = validated_data['price']
        if 'is_active' in validated_data:
            variant.is_active = validated_data['is_active']

        try:
            variant.save()
            return variant
        except IntegrityError as exc:
            logger.warning("Variant update failed: %s", exc)
            raise ValidationError({"sku": "A variant with this SKU already exists."})


def delete_variant(variant: ProductVariant) -> None:
    from orders.models import OrderItem

    with transaction.atomic():
        locked_product = Product.objects.select_for_update().get(id=variant.product_id)
        if locked_product.variants.count() <= 1:
            raise ValidationError({"detail": "Cannot delete the last variant of a product."})

        if OrderItem.objects.filter(variant=variant).exists() or StockMovement.objects.filter(variant=variant).exists():
            raise ValidationError({"detail": "Cannot delete variant with order or stock history. Deactivate it instead."})

        variant.delete()


def create_product_image(product: Product, validated_data: dict) -> ProductImage:
    variant_id = validated_data.get('variant_id')
    variant = None
    if variant_id:
        try:
            variant = ProductVariant.objects.get(id=variant_id, product=product)
        except ProductVariant.DoesNotExist:
            raise ValidationError({"variant_id": "Variant does not belong to this product."})

    image_url = validated_data.get('image_url')
    if not image_url and 'image' in validated_data:
        image_url = upload_image_to_cloudinary(validated_data['image'])

    if not image_url:
        raise ValidationError({"image_url": "Image file or valid image URL is required."})

    return ProductImage.objects.create(
        product=product,
        variant=variant,
        image_url=image_url,
        alt_text=validated_data.get('alt_text', '').strip(),
        position=validated_data.get('position', 0),
    )


def update_product_image(image: ProductImage, validated_data: dict) -> ProductImage:
    if 'variant_id' in validated_data:
        variant_id = validated_data['variant_id']
        if variant_id is None:
            image.variant = None
        else:
            try:
                image.variant = ProductVariant.objects.get(id=variant_id, product=image.product)
            except ProductVariant.DoesNotExist:
                raise ValidationError({"variant_id": "Variant does not belong to this product."})

    if 'image_url' in validated_data and validated_data['image_url']:
        image.image_url = validated_data['image_url']
    elif 'image' in validated_data and validated_data['image']:
        image.image_url = upload_image_to_cloudinary(validated_data['image'])

    if 'alt_text' in validated_data:
        image.alt_text = validated_data['alt_text'].strip()
    if 'position' in validated_data:
        image.position = validated_data['position']

    image.save()
    return image
    if 'alt_text' in validated_data:
        image.alt_text = validated_data['alt_text'].strip()
    if 'position' in validated_data:
        image.position = validated_data['position']

    image.save()
    return image


def delete_product_image(image: ProductImage) -> None:
    image.delete()


def create_stock_movement(validated_data: dict, user=None) -> StockMovement:
    variant_id = validated_data['variant_id']
    quantity_change = validated_data['quantity_change']
    reason = validated_data['reason']
    note = validated_data.get('note', '').strip()

    with transaction.atomic():
        try:
            variant = ProductVariant.objects.select_for_update().get(id=variant_id)
        except ProductVariant.DoesNotExist:
            raise ValidationError({"variant_id": "Product variant does not exist."})

        new_stock = variant.stock_quantity + quantity_change
        if new_stock < 0:
            raise ValidationError(
                {"quantity_change": f"Insufficient stock. Available quantity is {variant.stock_quantity}."}
            )

        variant.stock_quantity = new_stock
        variant.save(update_fields=['stock_quantity', 'updated_at'])

        movement = StockMovement.objects.create(
            variant=variant,
            quantity_change=quantity_change,
            reason=reason,
            note=note,
            created_by=user,
        )
        return movement

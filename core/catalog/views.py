from django.db.models import Max, Min, Q, Sum
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Product, ProductImage, ProductVariant, StockMovement
from .serializers import (
    CategoryRequestSerializer,
    CategoryResponseSerializer,
    CategoryUpdateRequestSerializer,
    CreateProductRequestSerializer,
    CreateVariantRequestSerializer,
    ProductDetailResponseSerializer,
    ProductImageRequestSerializer,
    ProductImageResponseSerializer,
    ProductImageUpdateRequestSerializer,
    ProductListResponseSerializer,
    StockMovementRequestSerializer,
    StockMovementResponseSerializer,
    UpdateProductRequestSerializer,
    UpdateVariantRequestSerializer,
    VariantResponseSerializer,
)
from .services import (
    create_category,
    create_product,
    create_product_image,
    create_stock_movement,
    create_variant,
    delete_category,
    delete_product,
    delete_product_image,
    delete_variant,
    update_category,
    update_product,
    update_product_image,
    update_variant,
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CategoryListCreateAPIView(APIView):
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get(self, request):
        include_inactive = request.query_params.get('include_inactive', '').lower() == 'true'
        qs = Category.objects.all()
        if not (request.user.is_authenticated and request.user.is_staff and include_inactive):
            qs = qs.filter(is_active=True)

        serializer = CategoryResponseSerializer(qs, many=True)
        return Response(
            {"message": "Categories fetched successfully.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CategoryRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = create_category(serializer.validated_data)
        return Response(
            {
                "message": "Category created successfully.",
                "data": CategoryResponseSerializer(category).data,
            },
            status=status.HTTP_201_CREATED,
        )


class CategoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ['PATCH', 'DELETE']:
            return [IsAdminUser()]
        return [AllowAny()]

    def _get_category(self, request, category_id: int) -> Category:
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            raise NotFound("Category not found.")

        is_staff = request.user.is_authenticated and request.user.is_staff
        if not category.is_active and not is_staff:
            raise NotFound("Category not found.")
        return category

    def get(self, request, id: int):
        category = self._get_category(request, id)
        return Response(
            {
                "message": "Category fetched successfully.",
                "data": CategoryResponseSerializer(category).data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, id: int):
        category = self._get_category(request, id)
        serializer = CategoryUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_category = update_category(category, serializer.validated_data)
        return Response(
            {
                "message": "Category updated successfully.",
                "data": CategoryResponseSerializer(updated_category).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id: int):
        category = self._get_category(request, id)
        delete_category(category)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductListCreateAPIView(APIView):
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get(self, request):
        include_inactive = request.query_params.get('include_inactive', '').lower() == 'true'
        is_staff = request.user.is_authenticated and request.user.is_staff

        qs = Product.objects.select_related('category').prefetch_related('variants', 'images')
        if not (is_staff and include_inactive):
            qs = qs.filter(is_active=True, category__is_active=True)

        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))

        category_param = request.query_params.get('category')
        if category_param:
            if category_param.isdigit():
                qs = qs.filter(category_id=int(category_param))
            else:
                qs = qs.filter(category__slug=category_param)

        in_stock = request.query_params.get('in_stock', '').lower()
        if in_stock == 'true':
            qs = qs.filter(variants__stock_quantity__gt=0, variants__is_active=True).distinct()

        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'name', '-name']:
            qs = qs.order_by(ordering)
        elif ordering in ['price', '-price']:
            qs = qs.annotate(min_price_annotated=Min('variants__price'))
            if ordering == 'price':
                qs = qs.order_by('min_price_annotated')
            else:
                qs = qs.annotate(max_price_annotated=Max('variants__price')).order_by('-max_price_annotated')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        product_items = []
        for p in (page if page is not None else qs):
            variants = [v for v in p.variants.all() if is_staff or v.is_active]
            prices = [v.price for v in variants]
            min_p = min(prices) if prices else None
            max_p = max(prices) if prices else None
            has_stock = any(v.stock_quantity > 0 for v in variants)
            images = list(p.images.all())
            main_img = images[0].image_url if images else None

            product_items.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "category_id": p.category_id,
                    "category_name": p.category.name,
                    "is_active": p.is_active,
                    "min_price": min_p,
                    "max_price": max_p,
                    "in_stock": has_stock,
                    "main_image_url": main_img,
                    "created_at": p.created_at,
                }
            )

        serializer = ProductListResponseSerializer(product_items, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)

        return Response(
            {"message": "Products fetched successfully.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CreateProductRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = create_product(serializer.validated_data)
        return Response(
            {
                "message": "Product created successfully.",
                "data": ProductDetailResponseSerializer(product).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ProductDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method in ['PATCH', 'DELETE']:
            return [IsAdminUser()]
        return [AllowAny()]

    def _get_product(self, request, product_id: int) -> Product:
        try:
            product = Product.objects.select_related('category').prefetch_related('variants', 'images').get(id=product_id)
        except Product.DoesNotExist:
            raise NotFound("Product not found.")

        is_staff = request.user.is_authenticated and request.user.is_staff
        if not is_staff:
            if not product.is_active or not product.category.is_active:
                raise NotFound("Product not found.")
        return product

    def get(self, request, id: int):
        product = self._get_product(request, id)
        is_staff = request.user.is_authenticated and request.user.is_staff

        data = {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "description": product.description,
            "is_active": product.is_active,
            "category": product.category,
            "variants": [v for v in product.variants.all() if is_staff or v.is_active],
            "images": product.images.all(),
            "created_at": product.created_at,
            "updated_at": product.updated_at,
        }
        return Response(
            {
                "message": "Product fetched successfully.",
                "data": ProductDetailResponseSerializer(data).data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, id: int):
        product = self._get_product(request, id)
        serializer = UpdateProductRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_product = update_product(product, serializer.validated_data)
        return Response(
            {
                "message": "Product updated successfully.",
                "data": ProductDetailResponseSerializer(updated_product).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id: int):
        product = self._get_product(request, id)
        delete_product(product)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductVariantCreateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, id: int):
        try:
            product = Product.objects.get(id=id)
        except Product.DoesNotExist:
            raise NotFound("Product not found.")

        serializer = CreateVariantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = create_variant(product, serializer.validated_data)
        return Response(
            {
                "message": "Variant created successfully.",
                "data": VariantResponseSerializer(variant).data,
            },
            status=status.HTTP_201_CREATED,
        )


class VariantDetailAPIView(APIView):
    permission_classes = [IsAdminUser]

    def _get_variant(self, variant_id: int) -> ProductVariant:
        try:
            return ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            raise NotFound("Variant not found.")

    def patch(self, request, id: int):
        variant = self._get_variant(id)
        serializer = UpdateVariantRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_variant = update_variant(variant, serializer.validated_data)
        return Response(
            {
                "message": "Variant updated successfully.",
                "data": VariantResponseSerializer(updated_variant).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id: int):
        variant = self._get_variant(id)
        delete_variant(variant)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductImageCreateAPIView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, id: int):
        try:
            product = Product.objects.get(id=id)
        except Product.DoesNotExist:
            raise NotFound("Product not found.")

        serializer = ProductImageRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = create_product_image(product, serializer.validated_data)
        return Response(
            {
                "message": "Image uploaded successfully.",
                "data": ProductImageResponseSerializer(image).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ProductImageDetailAPIView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_image(self, image_id: int) -> ProductImage:
        try:
            return ProductImage.objects.select_related('product').get(id=image_id)
        except ProductImage.DoesNotExist:
            raise NotFound("Product image not found.")

    def patch(self, request, id: int):
        image = self._get_image(id)
        serializer = ProductImageUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_image = update_product_image(image, serializer.validated_data)
        return Response(
            {
                "message": "Image updated successfully.",
                "data": ProductImageResponseSerializer(updated_image).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id: int):
        image = self._get_image(id)
        delete_product_image(image)
        return Response(status=status.HTTP_204_NO_CONTENT)


class StockMovementListCreateAPIView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = StockMovement.objects.select_related('variant', 'created_by')
        variant_id = request.query_params.get('variant')
        if variant_id:
            qs = qs.filter(variant_id=variant_id)

        reason = request.query_params.get('reason')
        if reason:
            qs = qs.filter(reason=reason)

        order_id = request.query_params.get('order')
        if order_id:
            qs = qs.filter(order_item__order_id=order_id)

        date_val = request.query_params.get('date')
        if date_val:
            qs = qs.filter(created_at__date=date_val)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        results = []
        for sm in (page if page is not None else qs):
            results.append(
                {
                    "id": sm.id,
                    "variant_id": sm.variant_id,
                    "variant_sku": sm.variant.sku,
                    "order_item_id": sm.order_item_id,
                    "quantity_change": sm.quantity_change,
                    "reason": sm.reason,
                    "note": sm.note,
                    "created_by_username": sm.created_by.username if sm.created_by else None,
                    "created_at": sm.created_at,
                }
            )

        serializer = StockMovementResponseSerializer(results, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)

        return Response(
            {"message": "Stock movements fetched successfully.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = StockMovementRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movement = create_stock_movement(serializer.validated_data, user=request.user)

        data = {
            "id": movement.id,
            "variant_id": movement.variant_id,
            "variant_sku": movement.variant.sku,
            "order_item_id": movement.order_item_id,
            "quantity_change": movement.quantity_change,
            "reason": movement.reason,
            "note": movement.note,
            "created_by_username": movement.created_by.username if movement.created_by else None,
            "created_at": movement.created_at,
        }
        return Response(
            {
                "message": "Stock movement recorded successfully.",
                "data": StockMovementResponseSerializer(data).data,
            },
            status=status.HTTP_201_CREATED,
        )

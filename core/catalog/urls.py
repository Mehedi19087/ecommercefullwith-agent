from django.urls import path

from .views import (
    CategoryDetailAPIView,
    CategoryListCreateAPIView,
    ProductDetailAPIView,
    ProductImageCreateAPIView,
    ProductImageDetailAPIView,
    ProductListCreateAPIView,
    ProductVariantCreateAPIView,
    StockMovementListCreateAPIView,
    VariantDetailAPIView,
)

urlpatterns = [
    # Categories
    path('categories/', CategoryListCreateAPIView.as_view(), name='category-list-create'),
    path('categories/<int:id>/', CategoryDetailAPIView.as_view(), name='category-detail'),
    # Products
    path('products/', ProductListCreateAPIView.as_view(), name='product-list-create'),
    path('products/<int:id>/', ProductDetailAPIView.as_view(), name='product-detail'),
    # Variants
    path('products/<int:id>/variants/', ProductVariantCreateAPIView.as_view(), name='product-variant-create'),
    path('variants/<int:id>/', VariantDetailAPIView.as_view(), name='variant-detail'),
    # Product Images
    path('products/<int:id>/images/', ProductImageCreateAPIView.as_view(), name='product-image-create'),
    path('product-images/<int:id>/', ProductImageDetailAPIView.as_view(), name='product-image-detail'),
    # Inventory
    path('staff/stock-movements/', StockMovementListCreateAPIView.as_view(), name='staff-stock-movements'),
]

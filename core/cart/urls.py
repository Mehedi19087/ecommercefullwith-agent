from django.urls import path

from .views import CartAPIView, CartItemDetailAPIView, CartItemListCreateAPIView

urlpatterns = [
    path('cart/', CartAPIView.as_view(), name='cart-detail'),
    path('cart/items/', CartItemListCreateAPIView.as_view(), name='cart-item-list-create'),
    path('cart/items/<int:id>/', CartItemDetailAPIView.as_view(), name='cart-item-detail'),
]

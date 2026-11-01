from django.urls import path

from .views import (
    CustomerOrderDetailAPIView,
    CustomerOrderListCreateAPIView,
    OrderCancelAPIView,
    StaffOrderDetailUpdateAPIView,
    StaffOrderListAPIView,
    StaffOrderPaymentAPIView,
    StaffOrderReturnAPIView,
    StaffPaymentRefundAPIView,
)

urlpatterns = [
    # Customer orders
    path('orders/', CustomerOrderListCreateAPIView.as_view(), name='customer-order-list-create'),
    path('orders/<uuid:number>/', CustomerOrderDetailAPIView.as_view(), name='customer-order-detail'),
    path('orders/<uuid:number>/cancel/', OrderCancelAPIView.as_view(), name='customer-order-cancel'),
    # Staff orders
    path('staff/orders/', StaffOrderListAPIView.as_view(), name='staff-order-list'),
    path('staff/orders/<uuid:number>/', StaffOrderDetailUpdateAPIView.as_view(), name='staff-order-detail-update'),
    path('staff/orders/<uuid:number>/returns/', StaffOrderReturnAPIView.as_view(), name='staff-order-return'),
    path('staff/orders/<uuid:number>/payments/', StaffOrderPaymentAPIView.as_view(), name='staff-order-payment'),
    path('staff/payments/<int:id>/refund/', StaffPaymentRefundAPIView.as_view(), name='staff-payment-refund'),
]

import uuid
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order, Payment
from .serializers import (
    CheckoutRequestSerializer,
    OrderDetailResponseSerializer,
    OrderReturnRequestSerializer,
    OrderSummaryResponseSerializer,
    PaymentResponseSerializer,
    StaffOrderUpdateRequestSerializer,
    StaffPaymentRequestSerializer,
    StaffRefundRequestSerializer,
)
from .services import (
    cancel_order,
    checkout,
    process_order_return,
    process_staff_refund,
    record_staff_payment,
    update_staff_order,
)
from .utils import is_order_owner


class StandardOrderPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CustomerOrderListCreateAPIView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        return [AllowAny()]

    def post(self, request):
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order, guest_order_token, is_new = checkout(request, serializer.validated_data)

        resp_status = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
        message = "Order placed successfully." if is_new else "Order retrieved from previous checkout."

        response = Response(
            {
                "message": message,
                "data": OrderDetailResponseSerializer(order).data,
                "guest_order_token": guest_order_token,
            },
            status=resp_status,
        )
        if guest_order_token:
            response.set_cookie('guest_order_token', guest_order_token, max_age=30*24*60*60, httponly=True, samesite='Lax')
            response['X-Guest-Order-Token'] = guest_order_token
        return response

    def get(self, request):
        qs = Order.objects.filter(user=request.user).prefetch_related('items', 'payments')
        paginator = StandardOrderPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = OrderSummaryResponseSerializer(page if page is not None else qs, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(
            {"message": "Orders fetched successfully.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )


class CustomerOrderDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, number: uuid.UUID):
        try:
            order = Order.objects.prefetch_related('items', 'payments').get(number=number)
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        if not is_order_owner(order, request):
            raise NotFound("Order not found.")

        return Response(
            {
                "message": "Order fetched successfully.",
                "data": OrderDetailResponseSerializer(order).data,
            },
            status=status.HTTP_200_OK,
        )


class OrderCancelAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, number: uuid.UUID):
        try:
            order = Order.objects.prefetch_related('items', 'payments').get(number=number)
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        is_staff = request.user.is_authenticated and request.user.is_staff
        if not (is_staff or is_order_owner(order, request)):
            raise NotFound("Order not found.")

        cancelled_order = cancel_order(order, user=request.user)
        return Response(
            {
                "message": "Order cancelled successfully.",
                "data": OrderDetailResponseSerializer(cancelled_order).data,
            },
            status=status.HTTP_200_OK,
        )


class StaffOrderListAPIView(APIView):
    permission_classes = [IsAdminUser]
    pagination_class = StandardOrderPagination

    def get(self, request):
        qs = Order.objects.prefetch_related('items', 'payments')

        order_status = request.query_params.get('status')
        if order_status:
            qs = qs.filter(status=order_status)

        phone = request.query_params.get('phone')
        if phone:
            qs = qs.filter(customer_phone__icontains=phone)

        number = request.query_params.get('number')
        if number:
            qs = qs.filter(number__icontains=number)

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        payment_status = request.query_params.get('payment_status')
        if payment_status:
            qs = qs.filter(payments__status=payment_status).distinct()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = OrderSummaryResponseSerializer(page if page is not None else qs, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)

        return Response(
            {"message": "Orders fetched successfully.", "data": serializer.data},
            status=status.HTTP_200_OK,
        )


class StaffOrderDetailUpdateAPIView(APIView):
    permission_classes = [IsAdminUser]

    def _get_order(self, number: uuid.UUID) -> Order:
        try:
            return Order.objects.prefetch_related('items', 'payments').get(number=number)
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

    def get(self, request, number: uuid.UUID):
        order = self._get_order(number)
        return Response(
            {
                "message": "Staff order fetched successfully.",
                "data": OrderDetailResponseSerializer(order).data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, number: uuid.UUID):
        order = self._get_order(number)
        serializer = StaffOrderUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_order = update_staff_order(order, serializer.validated_data)
        return Response(
            {
                "message": "Order updated successfully.",
                "data": OrderDetailResponseSerializer(updated_order).data,
            },
            status=status.HTTP_200_OK,
        )


class StaffOrderReturnAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, number: uuid.UUID):
        try:
            order = Order.objects.prefetch_related('items').get(number=number)
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        serializer = OrderReturnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        returned_order = process_order_return(order, serializer.validated_data, staff_user=request.user)
        return Response(
            {
                "message": "Order return processed successfully.",
                "data": OrderDetailResponseSerializer(returned_order).data,
            },
            status=status.HTTP_200_OK,
        )


class StaffOrderPaymentAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, number: uuid.UUID):
        try:
            order = Order.objects.prefetch_related('payments').get(number=number)
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        serializer = StaffPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = record_staff_payment(order, serializer.validated_data, staff_user=request.user)
        return Response(
            {
                "message": "Payment recorded successfully.",
                "data": PaymentResponseSerializer(payment).data,
            },
            status=status.HTTP_200_OK,
        )


class StaffPaymentRefundAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, id: int):
        serializer = StaffRefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = process_staff_refund(id, serializer.validated_data, staff_user=request.user)
        return Response(
            {
                "message": "Refund recorded successfully.",
                "data": PaymentResponseSerializer(payment).data,
            },
            status=status.HTTP_200_OK,
        )

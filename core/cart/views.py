from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AddToCartRequestSerializer,
    CartItemResponseSerializer,
    CartResponseSerializer,
    UpdateCartItemRequestSerializer,
)
from .services import add_item_to_cart, clear_cart, delete_cart_item, update_cart_item
from .utils import get_or_create_cart


class CartAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cart, new_token = get_or_create_cart(request)
        cart_data = CartResponseSerializer(cart).data
        response = Response(
            {"message": "Cart fetched successfully.", "data": cart_data},
            status=status.HTTP_200_OK,
        )
        if new_token:
            response.set_cookie('cart_token', new_token, httponly=True, samesite='Lax')
            response['X-Cart-Token'] = new_token
        return response

    def delete(self, request):
        cart, _ = get_or_create_cart(request)
        clear_cart(cart)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemListCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        cart, new_token = get_or_create_cart(request)
        serializer = AddToCartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart_item = add_item_to_cart(cart, serializer.validated_data)

        response = Response(
            {
                "message": "Item added to cart successfully.",
                "data": CartItemResponseSerializer(cart_item).data,
            },
            status=status.HTTP_201_CREATED,
        )
        if new_token:
            response.set_cookie('cart_token', new_token, httponly=True, samesite='Lax')
            response['X-Cart-Token'] = new_token
        return response


class CartItemDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def patch(self, request, id: int):
        cart, _ = get_or_create_cart(request)
        serializer = UpdateCartItemRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_item = update_cart_item(cart, id, serializer.validated_data)
        return Response(
            {
                "message": "Cart item updated successfully.",
                "data": CartItemResponseSerializer(updated_item).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id: int):
        cart, _ = get_or_create_cart(request)
        delete_cart_item(cart, id)
        return Response(status=status.HTTP_204_NO_CONTENT)

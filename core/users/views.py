from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Address
from .serializers import (
    AddressRequestSerializer,
    AddressResponseSerializer,
    AddressUpdateRequestSerializer,
    ChangePasswordRequestSerializer,
    LoginRequestSerializer,
    PasswordResetConfirmRequestSerializer,
    PasswordResetRequestSerializer,
    RegisterRequestSerializer,
    UpdateProfileRequestSerializer,
    UserResponseSerializer,
)
from .services import (
    authenticate_and_login_user,
    change_password,
    confirm_password_reset,
    create_address,
    delete_address,
    logout_user,
    register_user,
    request_password_reset,
    update_address,
    update_profile,
)


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_user(serializer.validated_data)
        return Response(
            {
                "message": "User registered successfully.",
                "data": UserResponseSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_and_login_user(request, serializer.validated_data)
        return Response(
            {
                "message": "Login successful.",
                "data": UserResponseSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout_user(request)
        return Response(
            {"message": "Logout successful.", "data": None},
            status=status.HTTP_200_OK,
        )


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "message": "User profile fetched successfully.",
                "data": UserResponseSerializer(request.user).data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        serializer = UpdateProfileRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = update_profile(request.user, serializer.validated_data)
        return Response(
            {
                "message": "User profile updated successfully.",
                "data": UserResponseSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_password(request, request.user, serializer.validated_data)
        return Response(
            {"message": "Password changed successfully.", "data": None},
            status=status.HTTP_200_OK,
        )


class PasswordResetAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(serializer.validated_data)
        return Response(
            {
                "message": "If the account exists, a password reset link has been sent.",
                "data": None,
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_password_reset(serializer.validated_data)
        return Response(
            {"message": "Password reset successfully.", "data": None},
            status=status.HTTP_200_OK,
        )


class AddressListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        addresses = Address.objects.filter(user=request.user)
        return Response(
            {
                "message": "Addresses fetched successfully.",
                "data": AddressResponseSerializer(addresses, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = AddressRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = create_address(request.user, serializer.validated_data)
        return Response(
            {
                "message": "Address created successfully.",
                "data": AddressResponseSerializer(address).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AddressDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_address(self, user, address_id: int) -> Address:
        try:
            return Address.objects.get(id=address_id, user=user)
        except Address.DoesNotExist:
            raise NotFound("Address not found.")

    def patch(self, request, id: int):
        address = self._get_address(request.user, id)
        serializer = AddressUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated_address = update_address(address, serializer.validated_data)
        return Response(
            {
                "message": "Address updated successfully.",
                "data": AddressResponseSerializer(updated_address).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, id: int):
        address = self._get_address(request.user, id)
        delete_address(address)
        return Response(status=status.HTTP_204_NO_CONTENT)

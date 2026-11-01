from django.urls import path

from .views import (
    AddressDetailAPIView,
    AddressListCreateAPIView,
    ChangePasswordAPIView,
    LoginAPIView,
    LogoutAPIView,
    PasswordResetAPIView,
    PasswordResetConfirmAPIView,
    RegisterAPIView,
    UserProfileAPIView,
)

urlpatterns = [
    path('auth/register/', RegisterAPIView.as_view(), name='auth-register'),
    path('auth/login/', LoginAPIView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutAPIView.as_view(), name='auth-logout'),
    path('auth/me/', UserProfileAPIView.as_view(), name='auth-me'),
    path('auth/password/change/', ChangePasswordAPIView.as_view(), name='auth-password-change'),
    path('auth/password/reset/', PasswordResetAPIView.as_view(), name='auth-password-reset'),
    path('auth/password/reset/confirm/', PasswordResetConfirmAPIView.as_view(), name='auth-password-reset-confirm'),
    path('addresses/', AddressListCreateAPIView.as_view(), name='address-list-create'),
    path('addresses/<int:id>/', AddressDetailAPIView.as_view(), name='address-detail'),
]

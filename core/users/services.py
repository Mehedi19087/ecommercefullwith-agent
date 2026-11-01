import logging
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from .models import Address

logger = logging.getLogger(__name__)
User = get_user_model()


def register_user(validated_data: dict) -> User:
    username = validated_data['username'].strip()
    email = validated_data['email'].strip().lower()
    password = validated_data['password']
    mobile_number = validated_data['mobile_number'].strip()
    first_name = validated_data.get('first_name', '').strip()
    last_name = validated_data.get('last_name', '').strip()

    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError({"username": "A user with this username already exists."})

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "A user with this email already exists."})

    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            mobile_number=mobile_number,
            first_name=first_name,
            last_name=last_name,
            is_staff=False,
            is_superuser=False,
        )
        return user
    except IntegrityError as exc:
        logger.warning("User registration failed: %s", exc)
        raise ValidationError({"non_field_errors": ["Could not register user due to database constraints."]})


def authenticate_and_login_user(request, validated_data: dict) -> User:
    username = validated_data['username']
    password = validated_data['password']

    user = authenticate(request, username=username, password=password)
    if not user:
        raise AuthenticationFailed("Invalid username or password.")
    if not user.is_active:
        raise AuthenticationFailed("User account is disabled.")

    login(request, user)
    return user


def logout_user(request) -> None:
    logout(request)


def update_profile(user: User, validated_data: dict) -> User:
    for field in ['first_name', 'last_name', 'mobile_number']:
        if field in validated_data:
            setattr(user, field, validated_data[field])
    user.save(update_fields=[f for f in ['first_name', 'last_name', 'mobile_number'] if f in validated_data])
    return user


def change_password(request, user: User, validated_data: dict) -> None:
    old_password = validated_data['old_password']
    new_password = validated_data['new_password']

    if not user.check_password(old_password):
        raise ValidationError({"old_password": "Wrong current password."})

    user.set_password(new_password)
    user.save(update_fields=['password'])
    update_session_auth_hash(request, user)


def request_password_reset(validated_data: dict) -> None:
    email = validated_data['email'].strip().lower()
    try:
        user = User.objects.get(email__iexact=email, is_active=True)
    except User.DoesNotExist:
        return

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    send_mail(
        subject="Password Reset Request",
        message=f"Use this UID: {uid} and token: {token} to reset your password.",
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
        recipient_list=[user.email],
        fail_silently=True,
    )


def confirm_password_reset(validated_data: dict) -> None:
    uid_str = validated_data['uid']
    token = validated_data['token']
    new_password = validated_data['new_password']

    try:
        uid = force_str(urlsafe_base64_decode(uid_str))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        raise ValidationError({"token": "Invalid or expired reset token."})

    if not default_token_generator.check_token(user, token):
        raise ValidationError({"token": "Invalid or expired reset token."})

    user.set_password(new_password)
    user.save(update_fields=['password'])


def create_address(user: User, validated_data: dict) -> Address:
    try:
        return Address.objects.create(user=user, **validated_data)
    except IntegrityError as exc:
        logger.warning("Address creation failed: %s", exc)
        raise ValidationError({"non_field_errors": ["Could not create address due to database constraints."]})


def update_address(address: Address, validated_data: dict) -> Address:
    for field, value in validated_data.items():
        setattr(address, field, value)
    address.save()
    return address


def delete_address(address: Address) -> None:
    address.delete()

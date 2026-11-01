from rest_framework import serializers


class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    mobile_number = serializers.CharField(max_length=20)


class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)


class UserResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    mobile_number = serializers.CharField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    date_joined = serializers.DateTimeField(read_only=True)


class UpdateProfileRequestSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    mobile_number = serializers.CharField(max_length=20, required=False)


class ChangePasswordRequestSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmRequestSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)


class AddressRequestSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    address_line = serializers.CharField()
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    city = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    country_code = serializers.CharField(max_length=2)


class AddressUpdateRequestSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    address_line = serializers.CharField(required=False)
    area = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country_code = serializers.CharField(max_length=2, required=False)


class AddressResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    recipient_name = serializers.CharField(read_only=True)
    phone = serializers.CharField(read_only=True)
    address_line = serializers.CharField(read_only=True)
    area = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    postal_code = serializers.CharField(read_only=True)
    country_code = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

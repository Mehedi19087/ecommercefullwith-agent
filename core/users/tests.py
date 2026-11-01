from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Address

User = get_user_model()


class AuthAndAddressAPITests(APITestCase):
    def setUp(self):
        self.user_data = {
            "username": "customer1",
            "email": "customer1@example.com",
            "password": "Password123!",
            "first_name": "John",
            "last_name": "Doe",
            "mobile_number": "1234567890",
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_register_success(self):
        url = reverse('auth-register')
        payload = {
            "username": "customer2",
            "email": "customer2@example.com",
            "password": "Password123!",
            "first_name": "Jane",
            "last_name": "Doe",
            "mobile_number": "0987654321",
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "User registered successfully.")
        self.assertEqual(response.data["data"]["username"], "customer2")

    def test_register_duplicate_username(self):
        url = reverse('auth-register')
        payload = self.user_data.copy()
        payload["email"] = "different@example.com"
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_and_logout(self):
        login_url = reverse('auth-login')
        response = self.client.post(
            login_url,
            {"username": "customer1", "password": "Password123!"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["username"], "customer1")

        # GET profile
        me_url = reverse('auth-me')
        response = self.client.get(me_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["email"], "customer1@example.com")

        # PATCH profile
        response = self.client.patch(me_url, {"first_name": "Johnny"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["first_name"], "Johnny")

        # Change password
        pwd_url = reverse('auth-password-change')
        response = self.client.post(
            pwd_url,
            {"old_password": "Password123!", "new_password": "NewPassword123!"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Logout
        logout_url = reverse('auth-logout')
        response = self.client.post(logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_flow(self):
        reset_url = reverse('auth-password-reset')
        response = self.client.post(reset_url, {"email": "customer1@example.com"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        confirm_url = reverse('auth-password-reset-confirm')
        response = self.client.post(
            confirm_url,
            {"uid": uid, "token": token, "new_password": "ResetPassword123!"},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ResetPassword123!"))

    def test_saved_addresses_crud(self):
        self.client.force_login(self.user)
        list_url = reverse('address-list-create')

        # Create address
        payload = {
            "recipient_name": "John Doe",
            "phone": "1234567890",
            "address_line": "123 Main St",
            "area": "Downtown",
            "city": "Metropolis",
            "postal_code": "12345",
            "country_code": "US",
        }
        response = self.client.post(list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        address_id = response.data["data"]["id"]

        # List addresses
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)

        # Update address
        detail_url = reverse('address-detail', kwargs={'id': address_id})
        response = self.client.patch(detail_url, {"city": "New Metropolis"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["city"], "New Metropolis")

        # Delete address
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Address.objects.filter(id=address_id).exists())

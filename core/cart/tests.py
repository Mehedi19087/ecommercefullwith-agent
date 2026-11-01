from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category, Product, ProductVariant
from .models import Cart, CartItem

User = get_user_model()


class CartAPITests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Books", slug="books", is_active=True)
        self.product = Product.objects.create(
            category=self.category,
            name="Django for Beginners",
            slug="django-for-beginners",
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="BOOK-DJ-01",
            options={"format": "Paperback"},
            price=Decimal("29.99"),
            stock_quantity=10,
            is_active=True,
        )
        self.customer = User.objects.create_user(
            username="buyer1",
            email="buyer1@example.com",
            password="BuyerPassword123!",
            mobile_number="5556667777",
        )

    def test_guest_cart_flow(self):
        cart_url = reverse('cart-detail')

        # Read initial guest cart - creates guest token
        res = self.client.get(cart_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('cart_token', res.cookies)
        guest_token = res.cookies['cart_token'].value

        # Add item to guest cart
        add_url = reverse('cart-item-list-create')
        res = self.client.post(add_url, {"variant_id": self.variant.id, "quantity": 2}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        item_id = res.data['data']['id']
        self.assertEqual(res.data['data']['quantity'], 2)

        # Adding same item again increments quantity
        res = self.client.post(add_url, {"variant_id": self.variant.id, "quantity": 3}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['data']['quantity'], 5)

        # Exceeding stock fails
        res = self.client.post(add_url, {"variant_id": self.variant.id, "quantity": 10}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Update cart item quantity
        item_url = reverse('cart-item-detail', kwargs={'id': item_id})
        res = self.client.patch(item_url, {"quantity": 4}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['quantity'], 4)

        # Read cart totals
        res = self.client.get(cart_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['total_items'], 4)
        self.assertEqual(Decimal(str(res.data['data']['subtotal'])), Decimal("119.96"))

        # Delete single item
        res = self.client.delete(item_url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Add again and clear whole cart
        self.client.post(add_url, {"variant_id": self.variant.id, "quantity": 1}, format='json')
        res = self.client.delete(cart_url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        res = self.client.get(cart_url)
        self.assertEqual(res.data['data']['total_items'], 0)

    def test_customer_cart_flow(self):
        self.client.force_login(self.customer)
        cart_url = reverse('cart-detail')
        add_url = reverse('cart-item-list-create')

        res = self.client.get(cart_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(add_url, {"variant_id": self.variant.id, "quantity": 1}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        cart = Cart.objects.get(user=self.customer)
        self.assertEqual(cart.items.count(), 1)

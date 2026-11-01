import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category, Product, ProductVariant
from cart.models import Cart, CartItem
from users.models import Address
from .models import Order, OrderItem, Payment

User = get_user_model()


class OrdersAPITests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff_admin",
            email="admin@example.com",
            password="AdminPassword123!",
            mobile_number="1112223333",
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username="shopper1",
            email="shopper1@example.com",
            password="ShopperPassword123!",
            mobile_number="2223334444",
        )
        self.address = Address.objects.create(
            user=self.customer,
            recipient_name="Shopper One",
            phone="2223334444",
            address_line="742 Evergreen Terrace",
            city="Springfield",
            country_code="US",
        )
        self.category = Category.objects.create(name="Gadgets", slug="gadgets", is_active=True)
        self.product = Product.objects.create(
            category=self.category,
            name="Smart Watch",
            slug="smart-watch",
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="WATCH-001",
            options={"color": "Silver"},
            price=Decimal("199.99"),
            stock_quantity=10,
            is_active=True,
        )

    def test_customer_checkout_and_cancellation(self):
        self.client.force_login(self.customer)
        # Put item in customer cart
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)

        checkout_key = str(uuid.uuid4())
        checkout_url = reverse('customer-order-list-create')
        payload = {
            "checkout_key": checkout_key,
            "address_id": self.address.id,
            "payment_method": "cod",
            "customer_note": "Please ring doorbell",
        }
        res = self.client.post(checkout_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order_number = res.data['data']['number']
        self.assertEqual(Decimal(str(res.data['data']['total'])), Decimal("399.98"))

        # Verify stock deducted
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 8)

        # Verify cart cleared
        self.assertEqual(cart.items.count(), 0)

        # Retry with same checkout_key is idempotent (200 OK)
        res_retry = self.client.post(checkout_url, payload, format='json')
        self.assertEqual(res_retry.status_code, status.HTTP_200_OK)
        self.assertEqual(res_retry.data['data']['number'], order_number)

        # Cancel order
        cancel_url = reverse('customer-order-cancel', kwargs={'number': order_number})
        res_cancel = self.client.post(cancel_url)
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cancel.data['data']['status'], Order.Status.CANCELLED)

        # Stock restored once
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 10)

        # Cancelling already cancelled order fails
        res_cancel_again = self.client.post(cancel_url)
        self.assertEqual(res_cancel_again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_guest_checkout_flow(self):
        cart_url = reverse('cart-detail')
        res_cart = self.client.get(cart_url)
        guest_cart_token = res_cart.cookies['cart_token'].value

        add_url = reverse('cart-item-list-create')
        self.client.post(add_url, {"variant_id": self.variant.id, "quantity": 1}, format='json')

        checkout_key = str(uuid.uuid4())
        checkout_url = reverse('customer-order-list-create')
        payload = {
            "checkout_key": checkout_key,
            "recipient_name": "Guest Customer",
            "phone": "9998887777",
            "delivery_address_line": "100 Broadway",
            "delivery_city": "New York",
            "delivery_country_code": "US",
            "payment_method": "manual",
        }
        res_checkout = self.client.post(checkout_url, payload, format='json')
        self.assertEqual(res_checkout.status_code, status.HTTP_201_CREATED)
        order_number = res_checkout.data['data']['number']
        self.assertIn('guest_order_token', res_checkout.cookies)

        # Read order as guest
        detail_url = reverse('customer-order-detail', kwargs={'number': order_number})
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.data['data']['customer_name'], "Guest Customer")

    def test_staff_order_management_and_returns_and_refunds(self):
        # Create an order
        self.client.force_login(self.customer)
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=3)

        checkout_url = reverse('customer-order-list-create')
        res = self.client.post(
            checkout_url,
            {"checkout_key": str(uuid.uuid4()), "address_id": self.address.id},
            format='json',
        )
        order_number = res.data['data']['number']
        item_id = res.data['data']['items'][0]['id']

        # Switch to staff
        self.client.force_login(self.staff_user)

        # Advance status: pending -> confirmed -> shipped -> delivered
        staff_order_url = reverse('staff-order-detail-update', kwargs={'number': order_number})
        res = self.client.patch(staff_order_url, {"status": "confirmed"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.patch(
            staff_order_url,
            {"status": "shipped", "courier_name": "FedEx", "tracking_number": "FX123456"},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.patch(staff_order_url, {"status": "delivered"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Record payment as succeeded
        payment_url = reverse('staff-order-payment', kwargs={'number': order_number})
        pending_payment = Payment.objects.get(order__number=order_number)
        res = self.client.post(
            payment_url,
            {"payment_id": pending_payment.id, "status": "succeeded", "reference": "TXN999"},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Process partial return: return 1 with restock
        return_url = reverse('staff-order-return', kwargs={'number': order_number})
        res = self.client.post(
            return_url,
            {"item_id": item_id, "quantity": 1, "restock_quantity": 1, "note": "Unopened return"},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['items'][0]['returned_quantity'], 1)

        # Process rest of return (2 units): changes order to 'returned'
        res = self.client.post(
            return_url,
            {"item_id": item_id, "quantity": 2, "restock_quantity": 2, "note": "Fully returned"},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['status'], Order.Status.RETURNED)

        # Refund succeeded payment
        refund_url = reverse('staff-payment-refund', kwargs={'id': pending_payment.id})
        res = self.client.post(
            refund_url,
            {"refund_reference": "REF123", "refund_note": "Customer returned all items"},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['status'], Payment.Status.REFUNDED)

        # Idempotent repeated refund
        res = self.client.post(refund_url, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['status'], Payment.Status.REFUNDED)

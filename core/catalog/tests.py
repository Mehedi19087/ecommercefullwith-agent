import io
from decimal import Decimal
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Product, ProductImage, ProductVariant, StockMovement

User = get_user_model()


def generate_test_image():
    file = io.BytesIO()
    image = Image.new('RGB', (100, 100), 'white')
    image.save(file, 'jpeg')
    file.seek(0)
    return SimpleUploadedFile('test.jpg', file.read(), content_type='image/jpeg')


class CatalogAPITests(APITestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@example.com',
            password='StaffPassword123!',
            mobile_number='1112223333',
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='customer_user',
            email='customer@example.com',
            password='CustomerPassword123!',
            mobile_number='4445556666',
        )

    def test_category_lifecycle(self):
        # Unauthenticated cannot create
        cat_url = reverse('category-list-create')
        res = self.client.post(cat_url, {"name": "Electronics", "slug": "electronics"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Staff can create
        self.client.force_login(self.staff_user)
        res = self.client.post(cat_url, {"name": "Electronics", "slug": "electronics"}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        parent_id = res.data['data']['id']

        # Create child category
        res = self.client.post(
            cat_url,
            {"name": "Phones", "slug": "phones", "parent_id": parent_id},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        child_id = res.data['data']['id']

        # Prevent cycle
        detail_url = reverse('category-detail', kwargs={'id': parent_id})
        res = self.client.patch(detail_url, {"parent_id": child_id}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Prevent delete parent when child exists
        res = self.client.delete(detail_url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Delete child then parent
        child_detail_url = reverse('category-detail', kwargs={'id': child_id})
        res = self.client.delete(child_detail_url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        res = self.client.delete(detail_url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_product_and_variant_flow(self):
        self.client.force_login(self.staff_user)
        category = Category.objects.create(name="Clothing", slug="clothing")

        prod_url = reverse('product-list-create')
        prod_payload = {
            "category_id": category.id,
            "name": "Cotton T-Shirt",
            "slug": "cotton-t-shirt",
            "description": "Comfortable tee",
            "initial_variant": {
                "sku": "TSHIRT-BLK-S",
                "options": {"color": "Black", "size": "S"},
                "price": "19.99",
            },
        }
        res = self.client.post(prod_url, prod_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        prod_id = res.data['data']['id']
        variant_1_id = res.data['data']['variants'][0]['id']

        # Add second variant
        var_create_url = reverse('product-variant-create', kwargs={'id': prod_id})
        var_payload = {
            "sku": "TSHIRT-BLK-M",
            "options": {"color": "Black", "size": "M"},
            "price": "21.99",
        }
        res = self.client.post(var_create_url, var_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        variant_2_id = res.data['data']['id']

        # Duplicate options rejected
        res = self.client.post(var_create_url, var_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Activate product
        detail_url = reverse('product-detail', kwargs={'id': prod_id})
        res = self.client.patch(detail_url, {"is_active": True}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['data']['is_active'])

        # Stock movement: receive stock
        sm_url = reverse('staff-stock-movements')
        res = self.client.post(
            sm_url,
            {
                "variant_id": variant_1_id,
                "quantity_change": 50,
                "reason": "received",
                "note": "Initial shipment",
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        var_1 = ProductVariant.objects.get(id=variant_1_id)
        self.assertEqual(var_1.stock_quantity, 50)

        # Negative stock damage movement
        res = self.client.post(
            sm_url,
            {
                "variant_id": variant_1_id,
                "quantity_change": -5,
                "reason": "damage",
                "note": "Water damage",
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        var_1.refresh_from_db()
        self.assertEqual(var_1.stock_quantity, 45)

        # Cannot delete variant 1 because it has stock movements
        var_1_url = reverse('variant-detail', kwargs={'id': variant_1_id})
        res = self.client.delete(var_1_url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Delete unused variant 2
        var_2_url = reverse('variant-detail', kwargs={'id': variant_2_id})
        res = self.client.delete(var_2_url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        # Now cannot delete variant 1 because it is the only variant left
        res = self.client.delete(var_1_url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_image_upload(self):
        self.client.force_login(self.staff_user)
        category = Category.objects.create(name="Shoes", slug="shoes")
        product = Product.objects.create(category=category, name="Running Shoes", slug="running-shoes")
        variant = ProductVariant.objects.create(
            product=product,
            sku="RUN-42",
            options={"size": "42"},
            price=Decimal("89.99"),
        )

        img_url = reverse('product-image-create', kwargs={'id': product.id})
        image_file = generate_test_image()
        res = self.client.post(
            img_url,
            {
                "image": image_file,
                "variant_id": variant.id,
                "alt_text": "Side view",
                "position": 1,
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        img_id = res.data['data']['id']
        self.assertTrue(res.data['data']['image_url'].startswith('http'))

        # Also test direct image_url input
        res_url = self.client.post(
            img_url,
            {
                "image_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
                "alt_text": "Cloudinary sample",
                "position": 2,
            },
            format='json',
        )
        self.assertEqual(res_url.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_url.data['data']['image_url'], "https://res.cloudinary.com/demo/image/upload/sample.jpg")

        detail_img_url = reverse('product-image-detail', kwargs={'id': img_id})
        res = self.client.patch(detail_img_url, {"alt_text": "Updated side view"}, format='multipart')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['data']['alt_text'], "Updated side view")

        res = self.client.delete(detail_img_url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

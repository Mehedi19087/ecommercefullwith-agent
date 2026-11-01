from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Product, ProductImage, ProductVariant, StockMovement


class Command(BaseCommand):
    help = "Seeds initial categories, products, variants, and stock for Bagalat Nijum."

    def handle(self, *args, **options):
        self.stdout.write("Seeding catalog data...")

        categories_data = [
            {"name": "Rice & grains", "slug": "rice"},
            {"name": "Oil & ghee", "slug": "oil"},
            {"name": "Spices & masala", "slug": "spices"},
            {"name": "Fish & seafood", "slug": "fish"},
            {"name": "Dairy & eggs", "slug": "dairy"},
            {"name": "Snacks & noodles", "slug": "snacks"},
        ]

        products_data = [
            {
                "category_slug": "rice",
                "name": "Chashi Chinigura Rice",
                "slug": "chashi-chinigura-rice",
                "description": "Bring a familiar aroma to the table. Chinigura rice is a much-loved choice for pulao, khichuri, and special family meals.",
                "sku": "CHASHI-1KG",
                "options": {"size": "1 kg"},
                "price": Decimal("18.50"),
                "stock": 50,
                "image": "https://www.spicevillage.eu/cdn/shop/products/chashi-indian-default-title-chashi-aromatic-rice-chinigura-1kg-25644680937626.jpg?v=1759731917",
            },
            {
                "category_slug": "oil",
                "name": "Rupchanda Soybean Oil",
                "slug": "rupchanda-soybean-oil",
                "description": "An everyday cooking companion, from a quick weekday stir-fry to a slow-cooked family curry.",
                "sku": "RUPCHANDA-2L",
                "options": {"size": "2 L"},
                "price": Decimal("24.90"),
                "stock": 50,
                "image": "https://foodpanda.dhmedia.io/image/darkstores/nv-global-catalog/bd/6d9ccfea-6475-4b84-87a0-469314c54fbb.jpg?height=480",
            },
            {
                "category_slug": "spices",
                "name": "Radhuni Turmeric Powder",
                "slug": "radhuni-turmeric-powder",
                "description": "The golden starting point for so many familiar recipes. Add warmth and colour to your dal and curries.",
                "sku": "RADHUNI-200G",
                "options": {"size": "200 g"},
                "price": Decimal("7.50"),
                "stock": 50,
                "image": "https://indianhouse.pl/cdn/shop/files/8_20240814_174350_0007.png?v=1749456581",
            },
            {
                "category_slug": "fish",
                "name": "Rui Fish · Bengali Cut",
                "slug": "rui-fish-steaks",
                "description": "For the fish curry you have been thinking about all week. Rui steaks in a traditional Bengali cut.",
                "sku": "RUI-1KG",
                "options": {"size": "1 kg"},
                "price": Decimal("32.00"),
                "stock": 50,
                "image": "https://image.cdn.shpy.in/416209/SKU-1088_0-1759725593172.png?format=webp",
            },
            {
                "category_slug": "dairy",
                "name": "Almarai Full Fat Milk",
                "slug": "almarai-full-fat-milk",
                "description": "Full-fat milk from a familiar Saudi household brand. Great for tea, breakfast, and cooking.",
                "sku": "ALMARAI-1L",
                "options": {"size": "1 L"},
                "price": Decimal("6.00"),
                "stock": 50,
                "image": "https://img.ananinja.com/media/ninja-catalog-42/Banmaly/B71/6281007120807_2.png?q=75&w=750",
            },
            {
                "category_slug": "snacks",
                "name": "Maggi Masala Noodles",
                "slug": "maggi-masala-noodles",
                "description": "A quick bowl of comfort for busy afternoons and late-night cravings. Classic masala noodles in an 8-pack.",
                "sku": "MAGGI-8PACK",
                "options": {"size": "8-pack"},
                "price": Decimal("12.50"),
                "stock": 50,
                "image": "https://foodpanda.dhmedia.io/image/nv-bd/Manisha/BD5BO18U.jpg?height=480",
            },
        ]

        with transaction.atomic():
            cats = {}
            for cd in categories_data:
                cat, _ = Category.objects.get_or_create(
                    slug=cd["slug"],
                    defaults={"name": cd["name"], "is_active": True},
                )
                cats[cd["slug"]] = cat

            for pd in products_data:
                category = cats[pd["category_slug"]]
                product, _ = Product.objects.get_or_create(
                    slug=pd["slug"],
                    defaults={
                        "category": category,
                        "name": pd["name"],
                        "description": pd["description"],
                        "is_active": True,
                    },
                )

                variant, created_var = ProductVariant.objects.get_or_create(
                    sku=pd["sku"],
                    defaults={
                        "product": product,
                        "options": pd["options"],
                        "price": pd["price"],
                        "stock_quantity": pd["stock"],
                        "is_active": True,
                    },
                )

                if created_var and pd["stock"] > 0:
                    StockMovement.objects.create(
                        variant=variant,
                        quantity_change=pd["stock"],
                        reason=StockMovement.Reason.RECEIVED,
                        note="Initial stock seeding",
                    )

                ProductImage.objects.get_or_create(
                    product=product,
                    variant=variant,
                    defaults={
                        "image_url": pd["image"],
                        "alt_text": pd["name"],
                        "position": 0,
                    },
                )

        self.stdout.write(self.style.SUCCESS("Catalog data successfully seeded!"))

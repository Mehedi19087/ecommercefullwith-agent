import json
import logging
import re
import urllib.request
from decimal import Decimal

import cloudinary
import cloudinary.uploader
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalog.cloudinary_service import is_cloudinary_configured
from catalog.models import Category, Product, ProductImage, ProductVariant, StockMovement

logger = logging.getLogger(__name__)

PANDA_CATEGORIES = [
    {
        "name": "Cooking Essentials",
        "slug": "cooking-essentials",
        "path": "cooking-essentials-467",
    },
    {
        "name": "Fresh Produce",
        "slug": "fresh-produce",
        "path": "fresh-311",
    },
    {
        "name": "Bakery",
        "slug": "bakery",
        "path": "bakery-235",
    },
    {
        "name": "Beverages",
        "slug": "beverages",
        "path": "beverages-288",
    },
    {
        "name": "Dairy & Breakfast",
        "slug": "dairy-breakfast",
        "path": "breakfast-468",
    },
    {
        "name": "Snacks",
        "slug": "snacks",
        "path": "snacks-238",
    },
]


def fetch_panda_products(cat_path: str, limit: int = 5):
    """
    Scrapes real products from Panda SA category page by parsing the Next.js state.
    """
    url = f"https://panda.sa/en/c/{cat_path}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")

    tag = r'\"products\":['
    start_idx = html.find(tag)
    if start_idx == -1:
        return []

    pos = start_idx + len(tag)
    chunk = html[pos : pos + 350000]
    cleaned = chunk.replace(r'\"', '"').replace(r'\\', '\\')

    products = []
    p_pos = 0
    seen = set()

    while len(products) < limit and p_pos < len(cleaned):
        brace_start = cleaned.find('{', p_pos)
        if brace_start == -1:
            break
        depth = 0
        in_str = False
        brace_end = -1
        for i in range(brace_start, len(cleaned)):
            c = cleaned[i]
            if c == '"' and (i == 0 or cleaned[i - 1] != '\\'):
                in_str = not in_str
            elif not in_str:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        brace_end = i
                        break
        if brace_end != -1:
            obj_str = cleaned[brace_start : brace_end + 1]
            try:
                obj = json.loads(obj_str)
                name = obj.get("name")
                varieties = obj.get("varieties", [])
                if name and varieties and name not in seen:
                    v = varieties[0]
                    price = v.get("price")
                    sku = v.get("sku")
                    img = v.get("imageURL") or (
                        v.get("images", [[]])[0][0] if v.get("images") else None
                    )
                    desc = v.get("description") or name
                    size = v.get("size")
                    unit = v.get("unit")
                    options = {}
                    if size and unit:
                        options = {"size": f"{size} {unit}"}
                    elif size:
                        options = {"size": str(size)}

                    if price and sku and float(price) > 0 and img:
                        seen.add(name)
                        img_clean = (
                            img.replace("Ar_small.jpg", "Ar_large.jpg").split("?")[0]
                        )
                        products.append(
                            {
                                "name": name.strip(),
                                "price": str(price),
                                "sku": f"PANDA-{sku}",
                                "description": desc.strip(),
                                "options": options,
                                "image": img_clean,
                            }
                        )
            except Exception:
                pass
            p_pos = brace_end + 1
        else:
            break

    return products


class Command(BaseCommand):
    help = "Scrapes live products from Panda SA and uploads images to Cloudinary."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=5,
            help="Number of products to import per category (default: 5)",
        )
        parser.add_argument(
            "--no-upload",
            action="store_true",
            help="Skip uploading images to Cloudinary and use direct URLs",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        no_upload = options["no_upload"]

        self.stdout.write(
            self.style.NOTICE(
                f"Starting catalog scrape from Panda SA ({limit} products per category)..."
            )
        )

        cloudinary_active = is_cloudinary_configured() and not no_upload
        if cloudinary_active:
            self.stdout.write(
                self.style.SUCCESS("Cloudinary is configured. Images will be uploaded.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Cloudinary not active or --no-upload specified. Using direct URLs."
                )
            )

        with transaction.atomic():
            self.stdout.write("Deleting old hardcoded products and categories...")
            StockMovement.objects.all().delete()
            ProductImage.objects.all().delete()
            ProductVariant.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()

            total_imported = 0

            for cat_data in PANDA_CATEGORIES:
                self.stdout.write(f"\nFetching category: {cat_data['name']}...")
                category = Category.objects.create(
                    name=cat_data["name"],
                    slug=cat_data["slug"],
                    is_active=True,
                )

                try:
                    scraped_items = fetch_panda_products(cat_data["path"], limit=limit)
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to fetch {cat_data['name']}: {exc}"
                        )
                    )
                    continue

                self.stdout.write(
                    f"Found {len(scraped_items)} items for {cat_data['name']}."
                )

                for item in scraped_items:
                    raw_slug = slugify(item["name"])[:160]
                    clean_slug = f"{raw_slug}-{item['sku'].lower()}"

                    product = Product.objects.create(
                        category=category,
                        name=item["name"],
                        slug=clean_slug,
                        description=item["description"],
                        is_active=True,
                    )

                    variant = ProductVariant.objects.create(
                        product=product,
                        sku=item["sku"],
                        options=item["options"],
                        price=Decimal(item["price"]),
                        stock_quantity=50,
                        is_active=True,
                    )

                    StockMovement.objects.create(
                        variant=variant,
                        quantity_change=50,
                        reason=StockMovement.Reason.RECEIVED,
                        note="Initial stock from Panda SA",
                    )

                    image_url = item["image"]
                    if cloudinary_active:
                        try:
                            self.stdout.write(
                                f"  Uploading image for {item['name'][:30]}..."
                            )
                            res = cloudinary.uploader.upload(
                                item["image"],
                                folder="ecommerce/products",
                                resource_type="image",
                            )
                            image_url = res.get("secure_url") or image_url
                        except Exception as upload_err:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  Cloudinary upload failed ({upload_err}). Falling back to direct URL."
                                )
                            )

                    ProductImage.objects.create(
                        product=product,
                        variant=variant,
                        image_url=image_url,
                        alt_text=item["name"][:200],
                        position=0,
                    )

                    total_imported += 1
                    self.stdout.write(
                        f"  + Added: {item['name'][:40]} (SAR {item['price']})"
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully seeded {total_imported} real products from Panda SA!"
            )
        )

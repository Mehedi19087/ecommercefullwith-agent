from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .cloudinary_service import upload_image_to_cloudinary
from .models import Category, Product, ProductImage, ProductVariant, StockMovement


class ProductImageForm(forms.ModelForm):
    upload_file = forms.ImageField(
        required=False,
        label="Upload Image to Cloudinary",
        help_text="Select a file to upload to Cloudinary, or enter an image URL below.",
    )

    class Meta:
        model = ProductImage
        fields = ['product', 'variant', 'upload_file', 'image_url', 'alt_text', 'position']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image_url'].required = False

    def clean(self):
        cleaned_data = super().clean()
        upload_file = cleaned_data.get('upload_file')
        image_url = cleaned_data.get('image_url')

        if upload_file:
            uploaded_url = upload_image_to_cloudinary(upload_file)
            cleaned_data['image_url'] = uploaded_url
        elif not image_url:
            raise forms.ValidationError("Please upload an image file or provide an image URL.")

        return cleaned_data


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageForm
    extra = 1
    fields = ['upload_file', 'image_url', 'image_preview', 'variant', 'alt_text', 'position']
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="max-height: 50px; border-radius: 4px;" />', obj.image_url)
        return "-"
    image_preview.short_description = "Preview"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['sku', 'options', 'price', 'stock_quantity', 'is_active']
    readonly_fields = ['stock_quantity']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active', 'category']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductVariantInline, ProductImageInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', 'product', 'price', 'stock_quantity', 'is_active', 'created_at']
    list_filter = ['is_active', 'product__category']
    search_fields = ['sku', 'product__name']
    readonly_fields = ['stock_quantity']


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    form = ProductImageForm
    list_display = ['id', 'image_preview', 'product', 'variant', 'position', 'created_at']
    list_filter = ['product']
    search_fields = ['product__name', 'alt_text', 'image_url']
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="max-height: 60px; border-radius: 4px;" />', obj.image_url)
        return "-"
    image_preview.short_description = "Preview"


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['id', 'variant', 'quantity_change', 'reason', 'note', 'created_by', 'created_at']
    list_filter = ['reason', 'created_at']
    search_fields = ['variant__sku', 'note']
    readonly_fields = ['variant', 'order_item', 'quantity_change', 'reason', 'note', 'created_by', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

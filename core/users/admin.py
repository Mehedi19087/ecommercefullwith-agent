from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from .models import Address, User


class AddressInline(admin.StackedInline):
    model = Address
    extra = 0


@admin.register(User)
class UserAdmin(DefaultUserAdmin):
    list_display = ['username', 'email', 'mobile_number', 'is_staff', 'is_active', 'date_joined']
    fieldsets = DefaultUserAdmin.fieldsets + (
        ('Contact Info', {'fields': ('mobile_number',)}),
    )
    inlines = [AddressInline]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['recipient_name', 'user', 'city', 'country_code', 'phone', 'created_at']
    search_fields = ['recipient_name', 'phone', 'city', 'user__username', 'user__email']

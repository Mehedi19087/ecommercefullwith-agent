from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=20)

    def __str__(self):
        return self.username


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
    )
    recipient_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    address_line = models.TextField()
    area = models.CharField(max_length=100, blank=True, default='')
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20, blank=True, default='')
    country_code = models.CharField(max_length=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient_name} - {self.city}, {self.country_code}"

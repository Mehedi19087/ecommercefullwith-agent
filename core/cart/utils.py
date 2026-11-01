import hashlib
import secrets
from django.db import transaction
from .models import Cart


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def get_cart_token_from_request(request) -> str | None:
    token = request.COOKIES.get('cart_token')
    if not token:
        token = request.headers.get('X-Cart-Token')
    return token.strip() if token else None


def get_or_create_cart(request) -> tuple[Cart, str | None]:
    """
    Returns (cart, new_guest_token).
    If user is authenticated, uses the user's cart.
    If user is guest, reads cart_token from cookie/header or generates a new one.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart, None

    token = get_cart_token_from_request(request)
    if token:
        token_hash = hash_token(token)
        cart = Cart.objects.filter(guest_token_hash=token_hash).first()
        if cart:
            return cart, None

    # Create new guest token and cart
    new_token = secrets.token_urlsafe(32)
    token_hash = hash_token(new_token)
    cart = Cart.objects.create(guest_token_hash=token_hash)
    return cart, new_token

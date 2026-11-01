import hashlib
import secrets
from .models import Order


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def get_guest_order_token_from_request(request) -> str | None:
    token = request.COOKIES.get('guest_order_token')
    if not token:
        token = request.headers.get('X-Guest-Order-Token')
    return token.strip() if token else None


def is_order_owner(order: Order, request) -> bool:
    if order.user and request.user.is_authenticated and order.user == request.user:
        return True

    if order.guest_access_token_hash:
        token = get_guest_order_token_from_request(request)
        if token and hash_token(token) == order.guest_access_token_hash:
            return True

    return False

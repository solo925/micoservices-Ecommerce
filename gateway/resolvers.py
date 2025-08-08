import requests
from functools import cache
from django.conf import settings

@cache
def resolve_products(obj, info):
    """Resolve products from the products service"""
    try:
        # In development, use localhost
        base_url = getattr(settings, 'PRODUCTS_SERVICE_URL', 'http://localhost:8000')
        response = requests.get(f'{base_url}/api/products/', timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Return empty list if service is unavailable
        return []

@cache
def resolve_orders(obj, info):
    """Resolve orders from the orders service"""
    try:
        # In development, use localhost
        base_url = getattr(settings, 'ORDERS_SERVICE_URL', 'http://localhost:8000')
        response = requests.get(f'{base_url}/api/orders/', timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Return empty list if service is unavailable
        return []

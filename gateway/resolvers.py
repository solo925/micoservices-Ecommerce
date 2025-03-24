import requests
from functools import cache

@cache
def resolve_products(obj, info):
    response = requests.get('http://products-service:8000/api/products/')
    return response.json()

@cache
def resolve_orders(obj, info, userId):
    response = requests.get(
        f'http://orders-service:8000/api/orders/?user_id={userId}'
    )
    return response.json()

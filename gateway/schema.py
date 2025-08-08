import graphene
from . import resolvers


class Product(graphene.ObjectType):
    """Product type for GraphQL"""
    id = graphene.ID()
    name = graphene.String()
    description = graphene.String()
    price = graphene.Float()
    stock = graphene.Int()
    created_at = graphene.String()
    updated_at = graphene.String()


class OrderItem(graphene.ObjectType):
    """OrderItem type for GraphQL"""
    id = graphene.ID()
    product_id = graphene.ID()
    product_name = graphene.String()
    quantity = graphene.Int()
    unit_price = graphene.Float()
    total_price = graphene.Float()


class Order(graphene.ObjectType):
    """Order type for GraphQL"""
    id = graphene.ID()
    order_number = graphene.String()
    customer_id = graphene.ID()
    status = graphene.String()
    total_amount = graphene.Float()
    created_at = graphene.String()
    updated_at = graphene.String()
    items = graphene.List(OrderItem)


class Query(graphene.ObjectType):
    """Root query type"""
    products = graphene.List(Product, description="List all products")
    orders = graphene.List(Order, description="List all orders")
    
    def resolve_products(self, info):
        """Resolve products from the products service"""
        return resolvers.resolve_products(info)
    
    def resolve_orders(self, info):
        """Resolve orders from the orders service"""
        return resolvers.resolve_orders(info)


# Create the schema
schema = graphene.Schema(query=Query)

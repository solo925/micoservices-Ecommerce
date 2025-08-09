import random
import json
import time
from datetime import datetime
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EcommerceUser(HttpUser):
    """Simulate e-commerce user behavior"""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between requests
    
    def on_start(self):
        """Initialize user session"""
        self.client.verify = False  # Disable SSL verification for testing
        self.auth_token = None
        self.user_id = None
        self.cart_items = []
        self.order_id = None
        
        # Login user
        self.login()
    
    def login(self):
        """Login user and get auth token"""
        login_data = {
            "email": f"testuser{random.randint(1, 1000)}@example.com",
            "password": "testpassword123"
        }
        
        # Try to login, if user doesn't exist, register first
        response = self.client.post("/api/auth/login/", json=login_data, name="Login")
        
        if response.status_code == 401:
            # User doesn't exist, register first
            register_data = {
                "email": login_data["email"],
                "password": login_data["password"],
                "first_name": f"Test{random.randint(1, 1000)}",
                "last_name": "User"
            }
            
            register_response = self.client.post("/api/auth/register/", json=register_data, name="Register")
            
            if register_response.status_code in [200, 201]:
                # Now try to login
                response = self.client.post("/api/auth/login/", json=login_data, name="Login After Register")
        
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get('access_token')
            self.user_id = data.get('user_id')
            
            # Set authorization header for future requests
            if self.auth_token:
                self.client.headers.update({'Authorization': f'Bearer {self.auth_token}'})
        else:
            logger.error(f"Login failed: {response.status_code} - {response.text}")
    
    @task(10)
    def browse_products(self):
        """Browse products catalog"""
        # List all products
        self.client.get("/api/products/", name="Browse Products")
        
        # Search products
        search_terms = ["laptop", "phone", "book", "shoes", "shirt"]
        search_term = random.choice(search_terms)
        self.client.get(f"/api/products/?search={search_term}", name="Search Products")
        
        # Get product details
        # Assuming we have product IDs 1-100
        product_id = random.randint(1, 100)
        self.client.get(f"/api/products/{product_id}/", name="Product Details")
    
    @task(8)
    def manage_cart(self):
        """Add/remove items from cart"""
        if random.choice([True, False]):
            # Add item to cart
            cart_item = {
                "product_id": random.randint(1, 100),
                "quantity": random.randint(1, 3)
            }
            
            response = self.client.post("/api/orders/cart/items/", json=cart_item, name="Add to Cart")
            
            if response.status_code in [200, 201]:
                self.cart_items.append(cart_item)
        else:
            # View cart
            self.client.get("/api/orders/cart/", name="View Cart")
    
    @task(5)
    def check_inventory(self):
        """Check inventory levels"""
        product_id = random.randint(1, 100)
        self.client.get(f"/api/inventory/items/{product_id}/", name="Check Inventory")
        
        # Check warehouse inventory
        self.client.get("/api/inventory/warehouses/", name="List Warehouses")
    
    @task(3)
    def place_order(self):
        """Place an order using SAGA pattern"""
        if not self.cart_items:
            # Add some items to cart first
            for _ in range(random.randint(1, 3)):
                cart_item = {
                    "product_id": random.randint(1, 100),
                    "quantity": random.randint(1, 2),
                    "unit_price": round(random.uniform(10, 100), 2)
                }
                cart_item["total_price"] = cart_item["quantity"] * cart_item["unit_price"]
                self.cart_items.append(cart_item)
        
        order_data = {
            "order": {
                "customer_name": f"Test User {self.user_id}",
                "customer_email": f"testuser{self.user_id}@example.com",
                "items": self.cart_items,
                "subtotal": sum(item["total_price"] for item in self.cart_items),
                "total_amount": sum(item["total_price"] for item in self.cart_items) * 1.1  # Add 10% tax
            },
            "payment": {
                "payment_method": "credit_card",
                "card_token": f"test_token_{random.randint(1000, 9999)}"
            }
        }
        
        response = self.client.post("/api/saga/order/", json=order_data, name="Place Order (SAGA)")
        
        if response.status_code == 200:
            data = response.json()
            self.order_id = data.get('order_id')
            saga_id = data.get('saga_id')
            
            # Check saga status
            if saga_id:
                self.client.get(f"/api/saga/status/{saga_id}/", name="Check SAGA Status")
            
            # Clear cart after successful order
            self.cart_items = []
    
    @task(2)
    def check_order_status(self):
        """Check order status"""
        if self.order_id:
            self.client.get(f"/api/orders/{self.order_id}/", name="Check Order Status")
        else:
            # List user's orders
            self.client.get("/api/orders/", name="List Orders")
    
    @task(2)
    def process_payment(self):
        """Process standalone payment"""
        payment_data = {
            "amount": round(random.uniform(10, 500), 2),
            "currency": "USD",
            "payment_method_type": "card",
            "provider": "stripe"
        }
        
        self.client.post("/api/payments/", json=payment_data, name="Process Payment")
    
    @task(1)
    def admin_operations(self):
        """Simulate admin operations"""
        # Check system health
        self.client.get("/api/gateway/health/", name="System Health Check")
        
        # Check metrics (if authorized)
        self.client.get("/prometheus/metrics/", name="Get Metrics")
        
        # Check resilience status
        self.client.get("/api/resilience/health/", name="Resilience Health")
        
        # Check service discovery
        self.client.get("/api/service-discovery/services/", name="Service Discovery")


class AdminUser(HttpUser):
    """Simulate admin user behavior"""
    
    wait_time = between(5, 15)  # Admins work slower
    weight = 1  # Lower weight, fewer admin users
    
    def on_start(self):
        """Initialize admin session"""
        self.client.verify = False
        self.auth_token = None
        
        # Login as admin
        self.admin_login()
    
    def admin_login(self):
        """Login as admin user"""
        admin_data = {
            "email": "admin@ecommerce.com",
            "password": "adminpassword123"
        }
        
        response = self.client.post("/api/auth/login/", json=admin_data, name="Admin Login")
        
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get('access_token')
            
            if self.auth_token:
                self.client.headers.update({'Authorization': f'Bearer {self.auth_token}'})
    
    @task(5)
    def monitor_system(self):
        """Monitor system health and metrics"""
        # Check various health endpoints
        endpoints = [
            "/api/gateway/health/",
            "/api/resilience/health/",
            "/api/saga/health/",
            "/api/service-discovery/health/"
        ]
        
        for endpoint in endpoints:
            self.client.get(endpoint, name=f"Health Check: {endpoint}")
    
    @task(3)
    def manage_inventory(self):
        """Manage inventory operations"""
        # List inventory items
        self.client.get("/api/inventory/items/", name="List Inventory")
        
        # Check low stock items
        self.client.get("/api/inventory/items/?low_stock=true", name="Low Stock Items")
        
        # Get inventory reports
        self.client.get("/api/inventory/reports/stock/", name="Stock Report")
    
    @task(3)
    def manage_orders(self):
        """Manage order operations"""
        # List recent orders
        self.client.get("/api/orders/?status=pending", name="Pending Orders")
        
        # Get order statistics
        self.client.get("/api/orders/statistics/", name="Order Statistics")
    
    @task(2)
    def monitor_payments(self):
        """Monitor payment operations"""
        # List recent payments
        self.client.get("/api/payments/", name="List Payments")
        
        # Get payment statistics
        self.client.get("/api/payments/statistics/", name="Payment Statistics")
    
    @task(2)
    def chaos_engineering(self):
        """Trigger chaos engineering experiments"""
        experiments = [
            {
                "type": "latency",
                "service_name": "products-service",
                "duration": 60,
                "latency_ms": 200,
                "probability": 0.1
            },
            {
                "type": "failure",
                "service_name": "inventory-service", 
                "duration": 30,
                "failure_rate": 0.05
            }
        ]
        
        experiment = random.choice(experiments)
        self.client.post("/api/resilience/chaos/", json=experiment, name="Chaos Experiment")
    
    @task(1)
    def test_saga_patterns(self):
        """Test SAGA patterns"""
        patterns = ["success", "inventory_failure", "payment_failure"]
        pattern = random.choice(patterns)
        
        self.client.post("/api/saga/test/", json={"pattern": pattern}, name=f"SAGA Test: {pattern}")


class APIUser(HttpUser):
    """Simulate API-only user (mobile app, external integrations)"""
    
    wait_time = between(2, 8)
    weight = 2  # Medium weight
    
    def on_start(self):
        """Initialize API session"""
        self.client.verify = False
        self.api_key = "test-api-key-123"
        
        # Set API key header
        self.client.headers.update({'X-API-Key': self.api_key})
    
    @task(10)
    def api_products(self):
        """Access products via API"""
        # Get products
        self.client.get("/api/products/", name="API: Get Products")
        
        # Get specific product
        product_id = random.randint(1, 100)
        self.client.get(f"/api/products/{product_id}/", name="API: Get Product")
    
    @task(5)
    def api_inventory(self):
        """Check inventory via API"""
        product_id = random.randint(1, 100)
        self.client.get(f"/api/inventory/items/{product_id}/", name="API: Check Inventory")
    
    @task(3)
    def api_orders(self):
        """Place orders via API"""
        order_data = {
            "customer_name": f"API Customer {random.randint(1, 1000)}",
            "customer_email": f"api{random.randint(1, 1000)}@example.com",
            "items": [
                {
                    "product_id": random.randint(1, 100),
                    "quantity": random.randint(1, 3),
                    "unit_price": round(random.uniform(10, 100), 2)
                }
            ]
        }
        
        # Calculate totals
        for item in order_data["items"]:
            item["total_price"] = item["quantity"] * item["unit_price"]
        
        order_data["subtotal"] = sum(item["total_price"] for item in order_data["items"])
        order_data["total_amount"] = order_data["subtotal"] * 1.1
        
        self.client.post("/api/orders/", json=order_data, name="API: Create Order")


# Event handlers for collecting additional metrics
@events.request.add_listener
def record_custom_metrics(request_type, name, response_time, response_length, response, 
                         context, exception, start_time, url, **kwargs):
    """Record custom metrics during load test"""
    
    # Record response times by endpoint
    if hasattr(record_custom_metrics, 'endpoint_times'):
        record_custom_metrics.endpoint_times = getattr(record_custom_metrics, 'endpoint_times', {})
    else:
        record_custom_metrics.endpoint_times = {}
    
    endpoint = name
    if endpoint not in record_custom_metrics.endpoint_times:
        record_custom_metrics.endpoint_times[endpoint] = []
    
    record_custom_metrics.endpoint_times[endpoint].append(response_time)
    
    # Log slow requests
    if response_time > 5000:  # > 5 seconds
        logger.warning(f"Slow request: {name} took {response_time}ms")
    
    # Log errors
    if exception:
        logger.error(f"Request failed: {name} - {str(exception)}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    logger.info("Load test starting...")
    
    # Initialize metrics collection
    record_custom_metrics.endpoint_times = {}
    record_custom_metrics.start_time = time.time()


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    logger.info("Load test completed.")
    
    # Calculate and log summary metrics
    if hasattr(record_custom_metrics, 'endpoint_times'):
        logger.info("=== ENDPOINT PERFORMANCE SUMMARY ===")
        
        for endpoint, times in record_custom_metrics.endpoint_times.items():
            if times:
                avg_time = sum(times) / len(times)
                max_time = max(times)
                min_time = min(times)
                p95_time = sorted(times)[int(len(times) * 0.95)] if len(times) > 0 else 0
                
                logger.info(f"{endpoint}:")
                logger.info(f"  Requests: {len(times)}")
                logger.info(f"  Avg: {avg_time:.2f}ms")
                logger.info(f"  Min: {min_time:.2f}ms") 
                logger.info(f"  Max: {max_time:.2f}ms")
                logger.info(f"  P95: {p95_time:.2f}ms")
    
    # Save detailed results
    if isinstance(environment.runner, MasterRunner):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f'load_test_results_{timestamp}.json'
        
        results = {
            'test_duration': time.time() - record_custom_metrics.start_time,
            'endpoint_metrics': record_custom_metrics.endpoint_times,
            'stats': environment.runner.stats.serialize_stats()
        }
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Detailed results saved to {results_file}")


# Custom task sets for different user scenarios
class BlackFridayScenario(HttpUser):
    """Simulate Black Friday high-traffic scenario"""
    
    wait_time = between(0.5, 2)  # Very fast interactions
    weight = 5  # High traffic
    
    @task(15)
    def flash_sale_browse(self):
        """Intensive browsing during flash sales"""
        # Rapid product browsing
        for _ in range(3):
            product_id = random.randint(1, 20)  # Popular products
            self.client.get(f"/api/products/{product_id}/", name="Flash Sale Browse")
    
    @task(10)
    def quick_purchase(self):
        """Quick purchase decisions"""
        # Simulate quick add-to-cart and checkout
        self.client.post("/api/orders/cart/items/", json={
            "product_id": random.randint(1, 20),
            "quantity": random.randint(1, 5)
        }, name="Quick Add to Cart")
        
        # Immediate checkout attempt
        if random.random() < 0.3:  # 30% proceed to checkout
            order_data = {
                "order": {
                    "customer_name": f"Flash Customer {random.randint(1, 10000)}",
                    "customer_email": f"flash{random.randint(1, 10000)}@example.com",
                    "items": [
                        {
                            "product_id": random.randint(1, 20),
                            "quantity": random.randint(1, 3),
                            "unit_price": round(random.uniform(50, 200), 2),
                            "total_price": 0
                        }
                    ],
                    "subtotal": 0,
                    "total_amount": 0
                },
                "payment": {
                    "payment_method": "credit_card"
                }
            }
            
            # Calculate totals
            for item in order_data["order"]["items"]:
                item["total_price"] = item["quantity"] * item["unit_price"]
            
            order_data["order"]["subtotal"] = sum(item["total_price"] for item in order_data["order"]["items"])
            order_data["order"]["total_amount"] = order_data["order"]["subtotal"]
            
            self.client.post("/api/saga/order/", json=order_data, name="Flash Sale Checkout")


if __name__ == "__main__":
    # This allows running the test directly
    import os
    os.system("locust -f comprehensive_load_test.py --host=http://localhost:8000")

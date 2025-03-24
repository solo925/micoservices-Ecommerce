from locust import HttpUser, task, between

class MicroserviceUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def browse_products(self):
        self.client.get("/products/")
    
    @task
    def create_order(self):
        self.client.post("/orders/", json={
            "items": [{"product_id": 1, "quantity": 2}]
        })

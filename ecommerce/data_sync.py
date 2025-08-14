"""
Data Synchronization Service for Distributed Microservices

This service handles cross-service data access and synchronization
when using distributed databases.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.db import connections
from django.core.cache import cache
import redis
from datetime import datetime

logger = logging.getLogger(__name__)


class DataSyncService:
    """
    Service for handling cross-service data access and synchronization
    in a distributed database architecture.
    """
    
    def __init__(self):
        self.redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        self.cache_ttl = 300  # 5 minutes
    
    def get_cross_service_data(self, service_name: str, model_name: str, 
                              filters: Dict[str, Any], fields: List[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve data from another microservice's database.
        
        Args:
            service_name: Name of the target microservice
            model_name: Name of the model to query
            filters: Filter criteria
            fields: Specific fields to retrieve
            
        Returns:
            List of data dictionaries
        """
        cache_key = f"cross_service:{service_name}:{model_name}:{hash(str(filters))}"
        
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data
        
        try:
            # Use the appropriate database connection
            with connections[service_name].cursor() as cursor:
                # Build the query
                select_fields = "*" if not fields else ", ".join(fields)
                where_clause = " AND ".join([f"{k} = %s" for k in filters.keys()])
                
                query = f"SELECT {select_fields} FROM {service_name}_{model_name}"
                if where_clause:
                    query += f" WHERE {where_clause}"
                
                # Execute query
                cursor.execute(query, list(filters.values()))
                
                # Fetch results
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                
                # Cache the results
                cache.set(cache_key, results, self.cache_ttl)
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get cross-service data from {service_name}: {e}")
            return []
    
    def publish_data_change_event(self, service_name: str, model_name: str, 
                                 action: str, data: Dict[str, Any]):
        """
        Publish data change events for cross-service synchronization.
        
        Args:
            service_name: Name of the service that changed
            model_name: Name of the model that changed
            action: Type of change (create, update, delete)
            data: Changed data
        """
        event_data = {
            'service': service_name,
            'model': model_name,
            'action': action,
            'data': data,
            'timestamp': str(datetime.now())
        }
        
        # Publish to Redis for other services to consume
        channel = f"data_sync:{service_name}:{model_name}"
        self.redis_client.publish(channel, json.dumps(event_data))
        
        # Also store in cache for immediate access
        cache_key = f"data_sync:{service_name}:{model_name}:{action}"
        cache.set(cache_key, event_data, self.cache_ttl)
    
    def subscribe_to_data_changes(self, service_name: str, model_name: str, 
                                 callback: callable):
        """
        Subscribe to data changes from another service.
        
        Args:
            service_name: Name of the service to monitor
            model_name: Name of the model to monitor
            callback: Function to call when data changes
        """
        channel = f"data_sync:{service_name}:{model_name}"
        
        # Store callback for later execution
        cache_key = f"callback:{service_name}:{model_name}"
        cache.set(cache_key, callback, self.cache_ttl)
    
    def invalidate_cross_service_cache(self, service_name: str, model_name: str):
        """
        Invalidate cached cross-service data.
        
        Args:
            service_name: Name of the service
            model_name: Name of the model
        """
        pattern = f"cross_service:{service_name}:{model_name}:*"
        
        # Get all matching cache keys
        keys = cache.keys(pattern)
        for key in keys:
            cache.delete(key)


class ServiceDataAccess:
    """
    Helper class for common cross-service data access patterns.
    """
    
    def __init__(self):
        self.sync_service = DataSyncService()
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user information from authentication service."""
        return self.sync_service.get_cross_service_data(
            'authentication', 'user', {'id': user_id}
        )
    
    def get_product_info(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get product information from inventory service."""
        return self.sync_service.get_cross_service_data(
            'inventory', 'product', {'id': product_id}
        )
    
    def get_order_summary(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Get order summary from orders service."""
        return self.sync_service.get_cross_service_data(
            'orders', 'order', {'id': order_id}
        )
    
    def get_payment_status(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """Get payment status from payments service."""
        return self.sync_service.get_cross_service_data(
            'payments', 'payment', {'id': payment_id}
        )


# Global instance for easy access
data_sync_service = DataSyncService()
service_data_access = ServiceDataAccess()

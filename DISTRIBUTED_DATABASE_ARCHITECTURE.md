# Distributed Database Architecture

## Overview

This document describes the migration from a single, centralized PostgreSQL database to a true distributed database architecture where each microservice has its own dedicated database.

## Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Microservice │    │   Microservice │    │   Microservice │
│   (Audit)      │    │   (Inventory)   │    │   (Orders)      │
│                 │    │                 │    │                 │
│   Database:    │    │   Database:     │    │   Database:     │
│   ecommerce_   │    │   ecommerce_    │    │   ecommerce_    │
│   audit        │    │   inventory     │    │   orders        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   Cluster       │
                    │                 │
                    │   Multiple      │
                    │   Databases     │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Redis Cache   │
                    │   (Data Sync)   │
                    └─────────────────┘
```

## Database Distribution

### Core Database (`ecommerce_core`)
- Django system tables
- Content types
- Sessions
- Admin tables
- Shared configuration

### Microservice Databases

| Service | Database Name | Purpose | Storage |
|---------|---------------|---------|---------|
| **Audit** | `ecommerce_audit` | Audit logs, security events, performance metrics | 3Gi |
| **Inventory** | `ecommerce_inventory` | Product catalog, stock levels, reservations | 5Gi |
| **Orders** | `ecommerce_orders` | Order management, order items, order history | 5Gi |
| **Payments** | `ecommerce_payments` | Payment processing, transactions, refunds | 3Gi |
| **Notifications** | `ecommerce_notifications` | User notifications, templates, preferences | 2Gi |
| **Events** | `ecommerce_events` | Event publishing, subscriptions, delivery tracking | 3Gi |
| **Service Discovery** | `ecommerce_service_discovery` | Service registry, health checks, metrics | 2Gi |
| **Authentication** | `ecommerce_auth` | User accounts, authentication, permissions | 2Gi |

## Key Components

### 1. Database Router (`ecommerce/routers.py`)

The database router directs all database operations to the appropriate microservice database based on the app label.

```python
class DatabaseRouter:
    app_database_mapping = {
        'audit': 'audit',
        'inventory': 'inventory',
        'orders': 'orders',
        'payments': 'payments',
        'notification': 'notifications',
        'events': 'events',
        'service_discovery': 'service_discovery',
        'authentication': 'authentication',
        'products': 'inventory',  # Products share inventory database
    }
```

### 2. Data Synchronization Service (`ecommerce/data_sync.py`)

Handles cross-service data access and synchronization when services need data from other microservices.

**Key Features:**
- Cross-service data retrieval
- Event-driven data change notifications
- Caching for performance
- Redis-based pub/sub for real-time updates

**Usage Example:**
```python
from ecommerce.data_sync import service_data_access

# Get user info from authentication service
user_info = service_data_access.get_user_info(user_id)

# Get product info from inventory service
product_info = service_data_access.get_product_info(product_id)
```

### 3. Cross-Service Data Access

When a microservice needs data from another service, it uses the DataSyncService:

```python
# Instead of direct database joins (which won't work across databases)
# Old way (single DB):
# user = User.objects.select_related('profile').get(id=user_id)

# New way (distributed DB):
user_data = data_sync_service.get_cross_service_data(
    'authentication', 'user', {'id': user_id}
)
```

## Migration Process

### Phase 1: Preparation
1. **Backup existing data**
2. **Create new database configuration**
3. **Deploy distributed PostgreSQL cluster**
4. **Update Django settings**

### Phase 2: Migration
1. **Run migration script**: `python scripts/migrate_to_distributed_db.py`
2. **Verify data integrity**
3. **Test all microservices**
4. **Update application code for cross-service access**

### Phase 3: Cleanup
1. **Remove old single database**
2. **Monitor performance**
3. **Optimize cross-service queries**

## Benefits of Distributed Databases

### ✅ **Advantages**

1. **Service Isolation**
   - Each microservice owns its data
   - Independent scaling and maintenance
   - No shared database locks or contention

2. **Technology Flexibility**
   - Different databases for different needs
   - Optimized schemas per service
   - Independent versioning and migrations

3. **Performance**
   - Reduced database size per service
   - Better query performance
   - Parallel processing capabilities

4. **Scalability**
   - Horizontal scaling per service
   - Independent resource allocation
   - Geographic distribution possibilities

5. **Fault Isolation**
   - Database failures don't affect all services
   - Independent backup and recovery
   - Better disaster recovery options

### ❌ **Challenges**

1. **Data Consistency**
   - Distributed transactions complexity
   - Eventual consistency requirements
   - Saga pattern implementation needed

2. **Cross-Service Queries**
   - No direct SQL joins across databases
   - Need for data synchronization
   - Potential performance overhead

3. **Operational Complexity**
   - Multiple database instances to manage
   - More complex monitoring and alerting
   - Backup and recovery coordination

4. **Development Complexity**
   - Need to understand data boundaries
   - Cross-service data access patterns
   - Testing complexity increases

## Data Consistency Patterns

### 1. Saga Pattern (Already Implemented)

For complex business transactions that span multiple services:

```python
# Example: Order processing saga
steps = [
    ReserveInventoryStep(),
    CreateOrderStep(),
    ProcessPaymentStep(),
    ConfirmInventoryStep(),
    SendNotificationStep()
]

saga = Saga("order_processing", steps, context)
result = await saga.execute()
```

### 2. Event-Driven Synchronization

Services publish events when data changes:

```python
# When inventory changes
data_sync_service.publish_data_change_event(
    'inventory', 'inventoryitem', 'update', 
    {'product_id': 123, 'quantity': 50}
)
```

### 3. Caching Strategy

Multi-level caching for cross-service data:

```python
# Redis cache for frequently accessed cross-service data
# Local cache for service-specific data
# Database for persistent storage
```

## Performance Considerations

### 1. Database Connections

Each microservice maintains its own database connection pool:

```python
DATABASES = {
    'inventory': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_inventory',
        'CONN_MAX_AGE': 600,  # 10 minutes
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
        }
    }
}
```

### 2. Query Optimization

- Use `select_related()` within the same database
- Use `DataSyncService` for cross-service data
- Implement appropriate caching strategies
- Monitor query performance per database

### 3. Connection Pooling

Consider using PgBouncer for connection pooling:

```yaml
# In Kubernetes deployment
- name: pgbouncer
  image: pgbouncer/pgbouncer:latest
  ports:
  - containerPort: 6432
```

## Monitoring and Observability

### 1. Database Metrics

Monitor each database independently:
- Connection count
- Query performance
- Storage usage
- Replication lag (if applicable)

### 2. Cross-Service Data Access

Track:
- Cross-service query frequency
- Cache hit rates
- Data synchronization latency
- Failed cross-service requests

### 3. Health Checks

Implement health checks for each database:

```python
def check_database_health(service_name):
    try:
        with connections[service_name].cursor() as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception:
        return False
```

## Security Considerations

### 1. Database Isolation

- Each database has its own user and permissions
- Network-level isolation between services
- Encrypted connections (TLS)

### 2. Access Control

- Service-to-service authentication
- Database-level role-based access control
- Audit logging for all cross-service access

### 3. Data Encryption

- Data at rest encryption
- Data in transit encryption
- Sensitive data field-level encryption

## Deployment

### 1. Kubernetes Deployment

```bash
# Deploy distributed databases
./k8s/deploy-distributed.sh

# Or manually
kubectl apply -f k8s/postgres-distributed.yaml
```

### 2. Database Initialization

The PostgreSQL StatefulSet automatically creates all required databases on startup.

### 3. Migration Script

```bash
# Run migration from single to distributed databases
python scripts/migrate_to_distributed_db.py
```

## Testing Strategy

### 1. Unit Tests

- Test each service with its own database
- Mock cross-service data access
- Test database routing logic

### 2. Integration Tests

- Test cross-service data synchronization
- Verify saga pattern execution
- Test event-driven updates

### 3. Performance Tests

- Load test each database independently
- Test cross-service query performance
- Monitor resource usage

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check database router configuration
   - Verify database names in settings
   - Check network connectivity

2. **Cross-Service Data Access Failures**
   - Verify DataSyncService configuration
   - Check Redis connectivity
   - Monitor cache hit rates

3. **Migration Issues**
   - Verify old database accessibility
   - Check PostgreSQL permissions
   - Review migration logs

### Debug Commands

```bash
# Check database connections
kubectl exec -it postgres-distributed-0 -- psql -U admin -d ecommerce_core

# View database router logs
kubectl logs -f deployment/gateway -n ecommerce

# Check Redis connectivity
kubectl exec -it redis-0 -- redis-cli ping
```

## Future Enhancements

### 1. Database Sharding

- Horizontal partitioning for high-volume services
- Geographic distribution for global deployments
- Read replicas for read-heavy workloads

### 2. Polyglot Persistence

- MongoDB for document storage
- Redis for caching and sessions
- Elasticsearch for search functionality
- Time-series databases for metrics

### 3. Advanced Synchronization

- Change Data Capture (CDC)
- Real-time streaming with Apache Kafka
- GraphQL federation for data access

## Conclusion

The distributed database architecture provides true microservice isolation while maintaining data consistency through well-defined patterns. The implementation includes:

- **Database routing** for automatic service isolation
- **Data synchronization** for cross-service data access
- **Saga patterns** for distributed transactions
- **Event-driven updates** for real-time synchronization
- **Comprehensive monitoring** for operational visibility

This architecture scales better, provides better fault isolation, and enables independent service evolution while maintaining the performance optimizations already implemented.

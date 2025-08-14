# Migration Quick Start Guide

## 🚀 Quick Migration to Distributed Databases

This guide will help you quickly migrate from your current single database setup to true distributed databases.

## Prerequisites

- ✅ Kubernetes cluster running
- ✅ kubectl configured and accessible
- ✅ Existing single database with data
- ✅ Python 3.8+ with Django environment

## 🎯 Migration Steps

### Step 1: Deploy Distributed Databases

```bash
# Navigate to your project directory
cd micoservices-Ecommerce

# Deploy the new distributed database architecture
./k8s/deploy-distributed.sh
```

**What this does:**
- Creates 9 separate PostgreSQL databases
- Sets up persistent storage for each database
- Configures the PostgreSQL cluster
- Deploys all microservices with new database configuration

### Step 2: Run Migration Script

```bash
# Install required dependencies
pip install psycopg2-binary

# Run the migration script
python scripts/migrate_to_distributed_db.py
```

**What this does:**
- Creates all new databases
- Copies data from old single database to new distributed databases
- Runs Django migrations on each database
- Verifies data integrity

### Step 3: Verify Migration

```bash
# Check database status
kubectl get pods -n ecommerce | grep postgres

# Check database connections
kubectl exec -it postgres-distributed-0 -- psql -U admin -d ecommerce_core -c "\l"

# Test microservice connectivity
kubectl logs -f deployment/gateway -n ecommerce
```

## 🔧 Configuration Changes Made

### 1. Database Settings (`ecommerce/settings.py`)

**Before (Single DB):**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce',  # Single database
        'USER': 'admin',
        'PASSWORD': 'securepass123',
        'HOST': 'postgres-service',
        'PORT': '5432'
    }
}
```

**After (Distributed DBs):**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_core',  # Core system database
        # ... other settings
    },
    'audit': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_audit',  # Audit service database
        # ... other settings
    },
    'inventory': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_inventory',  # Inventory service database
        # ... other settings
    },
    # ... 6 more service databases
}

# Database routing
DATABASE_ROUTERS = ['ecommerce.routers.DatabaseRouter']
```

### 2. New Files Created

- `ecommerce/routers.py` - Database routing logic
- `ecommerce/data_sync.py` - Cross-service data synchronization
- `k8s/postgres-distributed.yaml` - Distributed database deployment
- `k8s/deploy-distributed.sh` - Deployment script
- `scripts/migrate_to_distributed_db.py` - Migration script

## 📊 Database Distribution

| Service | Database | Tables |
|---------|----------|---------|
| **Core** | `ecommerce_core` | Django system, admin, sessions |
| **Audit** | `ecommerce_audit` | Audit logs, security events |
| **Inventory** | `ecommerce_inventory` | Products, stock, reservations |
| **Orders** | `ecommerce_orders` | Orders, order items |
| **Payments** | `ecommerce_payments` | Payments, transactions |
| **Notifications** | `ecommerce_notifications` | Notifications, templates |
| **Events** | `ecommerce_events` | Events, subscriptions |
| **Service Discovery** | `ecommerce_service_discovery` | Service registry, health |
| **Authentication** | `ecommerce_auth` | Users, permissions |

## 🔄 Cross-Service Data Access

### Before (Single DB - Direct Joins)
```python
# This won't work anymore across different databases
user = User.objects.select_related('profile').get(id=user_id)
product = Product.objects.select_related('inventory').get(id=product_id)
```

### After (Distributed DBs - DataSyncService)
```python
from ecommerce.data_sync import service_data_access

# Get user info from authentication service
user_info = service_data_access.get_user_info(user_id)

# Get product info from inventory service
product_info = service_data_access.get_product_info(product_id)
```

## 🧪 Testing Your Migration

### 1. Test Database Routing

```python
# In Django shell
python manage.py shell

from audit.models import AuditLog
from inventory.models import InventoryItem

# These should use different databases automatically
audit_log = AuditLog.objects.create(message="Test")
inventory_item = InventoryItem.objects.create(product_id="123", quantity=10)
```

### 2. Test Cross-Service Access

```python
from ecommerce.data_sync import service_data_access

# Test getting data from other services
user_data = service_data_access.get_user_info(1)
product_data = service_data_access.get_product_info("123")
```

### 3. Test Saga Patterns

```python
from saga.patterns import OrderProcessingSaga

# Test distributed transaction
saga = OrderProcessingSaga.create_order(order_data, payment_data)
```

## 🚨 Common Issues & Solutions

### Issue 1: Database Connection Errors
```bash
# Check if databases exist
kubectl exec -it postgres-distributed-0 -- psql -U admin -d postgres -c "\l"

# Check database router logs
kubectl logs -f deployment/gateway -n ecommerce
```

**Solution:** Verify database names in `settings.py` match the created databases.

### Issue 2: Cross-Service Data Access Fails
```bash
# Check Redis connectivity
kubectl exec -it redis-0 -- redis-cli ping

# Check DataSyncService logs
kubectl logs -f deployment/gateway -n ecommerce | grep DataSync
```

**Solution:** Ensure Redis is running and accessible.

### Issue 3: Migration Script Fails
```bash
# Check PostgreSQL permissions
kubectl exec -it postgres-distributed-0 -- psql -U admin -d postgres -c "\du"

# Check migration logs
python scripts/migrate_to_distributed_db.py --verbose
```

**Solution:** Verify PostgreSQL user has CREATE DATABASE permissions.

## 📈 Performance Monitoring

### 1. Database Performance
```bash
# Monitor each database independently
kubectl exec -it postgres-distributed-0 -- psql -U admin -d ecommerce_audit -c "SELECT * FROM pg_stat_activity;"
```

### 2. Cross-Service Performance
```python
# Monitor cross-service data access
from ecommerce.data_sync import data_sync_service

# Check cache hit rates
cache_stats = data_sync_service.get_cache_stats()
```

### 3. Resource Usage
```bash
# Monitor resource usage per database
kubectl top pods -n ecommerce | grep postgres
kubectl get pvc -n ecommerce
```

## 🔒 Security Considerations

### 1. Database Isolation
- Each database has its own storage
- Network-level isolation between services
- Independent backup and recovery

### 2. Access Control
- Service-to-service authentication
- Database-level permissions
- Audit logging for all access

## 📝 Post-Migration Checklist

- [ ] All microservices are running
- [ ] Database routing is working correctly
- [ ] Cross-service data access is functional
- [ ] Saga patterns are executing properly
- [ ] Performance is acceptable
- [ ] Monitoring is in place
- [ ] Backups are configured for each database
- [ ] Old single database is backed up
- [ ] Team is trained on new patterns

## 🎉 Migration Complete!

Once you've completed all steps and verified functionality:

1. **Monitor performance** for the first 24-48 hours
2. **Test all business workflows** thoroughly
3. **Update documentation** for your team
4. **Plan cleanup** of old single database
5. **Celebrate** your new distributed architecture! 🎊

## 📚 Additional Resources

- [Distributed Database Architecture](DISTRIBUTED_DATABASE_ARCHITECTURE.md) - Detailed architecture documentation
- [Performance Optimization Summary](PERFORMANCE_OPTIMIZATION_SUMMARY.md) - Performance improvements
- [System Design](SYSTEM_DESIGN.md) - Overall system architecture

## 🆘 Need Help?

If you encounter issues during migration:

1. Check the troubleshooting section above
2. Review Kubernetes logs: `kubectl logs -f deployment/[service-name] -n ecommerce`
3. Verify database connectivity: `kubectl exec -it postgres-distributed-0 -- psql -U admin -d ecommerce_core`
4. Check Redis status: `kubectl exec -it redis-0 -- redis-cli ping`

**Happy Migrating! 🚀**

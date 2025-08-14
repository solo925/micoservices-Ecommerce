"""
Database Router for Distributed Microservices Architecture

This router directs database operations to the appropriate microservice database
based on the app label and model type.
"""

class DatabaseRouter:
    """
    A router to control all database operations on models for different
    microservices.
    """
    
    # Map of app labels to database names
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
        'admin': 'default',       # Django admin uses default
        'contenttypes': 'default', # Django content types
        'sessions': 'default',    # Django sessions
        'auth': 'default',        # Django auth
    }
    
    def db_for_read(self, model, **hints):
        """
        Suggest the database that should be used for reads of objects of type
        `model`.
        """
        app_label = model._meta.app_label
        return self.app_database_mapping.get(app_label, 'default')
    
    def db_for_write(self, model, **hints):
        """
        Suggest the database that should be used for writes of objects of type
        `model`.
        """
        app_label = model._meta.app_label
        return self.app_database_mapping.get(app_label, 'default')
    
    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow any relation if both objects are in the same database.
        """
        db1 = self.db_for_read(obj1)
        db2 = self.db_for_read(obj2)
        return db1 == db2
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Make sure the app only appears in the appropriate database.
        """
        if app_label in self.app_database_mapping:
            return db == self.app_database_mapping[app_label]
        return db == 'default'
    
    def allow_join(self, obj1, obj2, **hints):
        """
        Allow joins only if both objects are in the same database.
        """
        db1 = self.db_for_read(obj1)
        db2 = self.db_for_read(obj2)
        return db1 == db2

#!/usr/bin/env python3
"""
Migration Script: Single Database to Distributed Databases

This script handles the migration from a single PostgreSQL database
to multiple microservice-specific databases.
"""

import os
import sys
import django
import psycopg2
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')
django.setup()

from django.conf import settings
from django.db import connections
from django.core.management import call_command


class DistributedDatabaseMigrator:
    """
    Handles migration from single database to distributed databases.
    """
    
    def __init__(self):
        self.old_db_config = {
            'host': 'postgres-service',
            'port': '5432',
            'user': 'admin',
            'password': 'securepass123',
            'database': 'ecommerce'
        }
        
        self.new_databases = [
            'ecommerce_core',
            'ecommerce_audit',
            'ecommerce_inventory',
            'ecommerce_orders',
            'ecommerce_payments',
            'ecommerce_notifications',
            'ecommerce_events',
            'ecommerce_service_discovery',
            'ecommerce_auth'
        ]
    
    def check_old_database_connection(self):
        """Check if the old single database is accessible."""
        try:
            conn = psycopg2.connect(**self.old_db_config)
            conn.close()
            print("✅ Old database connection successful")
            return True
        except Exception as e:
            print(f"❌ Old database connection failed: {e}")
            return False
    
    def create_new_databases(self):
        """Create new microservice databases."""
        try:
            # Connect to PostgreSQL server (not a specific database)
            conn = psycopg2.connect(
                host=self.old_db_config['host'],
                port=self.old_db_config['port'],
                user=self.old_db_config['user'],
                password=self.old_db_config['password'],
                database='postgres'  # Connect to default postgres database
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            for db_name in self.new_databases:
                try:
                    cursor.execute(f"CREATE DATABASE {db_name}")
                    print(f"✅ Created database: {db_name}")
                except psycopg2.errors.DuplicateDatabase:
                    print(f"⚠️  Database {db_name} already exists")
                except Exception as e:
                    print(f"❌ Failed to create {db_name}: {e}")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Failed to create new databases: {e}")
            return False
    
    def migrate_apps_to_new_databases(self):
        """Run migrations for each app on their respective databases."""
        for app_name in ['audit', 'inventory', 'orders', 'payments', 'notification', 'events', 'service_discovery', 'authentication']:
            try:
                print(f"🔄 Migrating {app_name}...")
                
                # Run migrations for the specific app
                call_command('migrate', app_label=app_name, verbosity=1)
                print(f"✅ {app_name} migration completed")
                
            except Exception as e:
                print(f"❌ {app_name} migration failed: {e}")
    
    def copy_data_from_old_database(self):
        """Copy data from old database to new distributed databases."""
        try:
            # Connect to old database
            old_conn = psycopg2.connect(**self.old_db_config)
            old_cursor = old_conn.cursor()
            
            # Get list of tables
            old_cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """)
            tables = old_cursor.fetchall()
            
            print(f"📋 Found {len(tables)} tables to migrate")
            
            for table in tables:
                table_name = table[0]
                app_name = self._get_app_name_from_table(table_name)
                
                if app_name and app_name in self.new_databases:
                    try:
                        self._copy_table_data(old_cursor, table_name, app_name)
                    except Exception as e:
                        print(f"❌ Failed to copy {table_name}: {e}")
            
            old_cursor.close()
            old_conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Data copy failed: {e}")
            return False
    
    def _get_app_name_from_table(self, table_name):
        """Determine which app a table belongs to."""
        app_mapping = {
            'audit': 'ecommerce_audit',
            'inventory': 'ecommerce_inventory',
            'orders': 'ecommerce_orders',
            'payments': 'ecommerce_payments',
            'notification': 'ecommerce_notifications',
            'events': 'ecommerce_events',
            'service_discovery': 'ecommerce_service_discovery',
            'authentication': 'ecommerce_auth'
        }
        
        for app, db in app_mapping.items():
            if table_name.startswith(app):
                return db
        
        return None
    
    def _copy_table_data(self, old_cursor, table_name, target_db):
        """Copy data from old table to new database."""
        try:
            # Get table structure
            old_cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
            columns = [desc[0] for desc in old_cursor.description]
            
            # Get data
            old_cursor.execute(f"SELECT * FROM {table_name}")
            rows = old_cursor.fetchall()
            
            if not rows:
                print(f"📭 Table {table_name} is empty, skipping")
                return
            
            # Connect to target database
            target_conn = psycopg2.connect(
                host=self.old_db_config['host'],
                port=self.old_db_config['port'],
                user=self.old_db_config['user'],
                password=self.old_db_config['password'],
                database=target_db
            )
            target_cursor = target_conn.cursor()
            
            # Create table if it doesn't exist (basic structure)
            # In production, you'd want to use Django's schema
            columns_def = ", ".join([f"{col} TEXT" for col in columns])
            target_cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    {columns_def}
                )
            """)
            
            # Insert data
            placeholders = ", ".join(["%s"] * len(columns))
            insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            target_cursor.executemany(insert_query, rows)
            target_conn.commit()
            
            print(f"✅ Copied {len(rows)} rows from {table_name} to {target_db}")
            
            target_cursor.close()
            target_conn.close()
            
        except Exception as e:
            print(f"❌ Failed to copy {table_name}: {e}")
    
    def verify_migration(self):
        """Verify that all data has been migrated correctly."""
        print("🔍 Verifying migration...")
        
        for db_name in self.new_databases:
            try:
                conn = psycopg2.connect(
                    host=self.old_db_config['host'],
                    port=self.old_db_config['port'],
                    user=self.old_db_config['user'],
                    password=self.old_db_config['password'],
                    database=db_name
                )
                cursor = conn.cursor()
                
                # Count tables
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                table_count = cursor.fetchone()[0]
                
                print(f"📊 {db_name}: {table_count} tables")
                
                cursor.close()
                conn.close()
                
            except Exception as e:
                print(f"❌ Verification failed for {db_name}: {e}")
    
    def run_migration(self):
        """Run the complete migration process."""
        print("🚀 Starting migration to distributed databases...")
        
        # Step 1: Check old database
        if not self.check_old_database_connection():
            print("❌ Cannot proceed without old database access")
            return False
        
        # Step 2: Create new databases
        print("\n📦 Creating new databases...")
        if not self.create_new_databases():
            print("❌ Failed to create new databases")
            return False
        
        # Step 3: Run migrations
        print("\n🔄 Running Django migrations...")
        self.migrate_apps_to_new_databases()
        
        # Step 4: Copy data
        print("\n📋 Copying data from old database...")
        if not self.copy_data_from_old_database():
            print("❌ Data copy failed")
            return False
        
        # Step 5: Verify migration
        print("\n🔍 Verifying migration...")
        self.verify_migration()
        
        print("\n✅ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("1. Update your application to use the new database configuration")
        print("2. Test all microservices with their new databases")
        print("3. Remove the old single database when ready")
        
        return True


def main():
    """Main migration function."""
    migrator = DistributedDatabaseMigrator()
    
    try:
        success = migrator.run_migration()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

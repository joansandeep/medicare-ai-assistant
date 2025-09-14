# Database Configuration for Free Deployment
import os

# Free Database Options Configuration
DATABASE_CONFIGS = {
    'planetscale': {
        'host': os.environ.get('PLANETSCALE_HOST'),
        'user': os.environ.get('PLANETSCALE_USERNAME'),
        'password': os.environ.get('PLANETSCALE_PASSWORD'),
        'database': os.environ.get('PLANETSCALE_DATABASE'),
        'port': 3306,
        'ssl_disabled': False,
        'autocommit': True
    },
    'railway': {
        'host': os.environ.get('RAILWAY_DB_HOST'),
        'user': os.environ.get('RAILWAY_DB_USER'),
        'password': os.environ.get('RAILWAY_DB_PASSWORD'),
        'database': os.environ.get('RAILWAY_DB_NAME'),
        'port': int(os.environ.get('RAILWAY_DB_PORT', 5432)),
        'autocommit': True
    },
    'aiven': {
        'host': os.environ.get('AIVEN_HOST'),
        'user': os.environ.get('AIVEN_USER'),
        'password': os.environ.get('AIVEN_PASSWORD'),
        'database': os.environ.get('AIVEN_DATABASE'),
        'port': int(os.environ.get('AIVEN_PORT', 3306)),
        'ssl_disabled': False,
        'autocommit': True
    }
}

def get_db_config():
    """Get database configuration based on environment"""
    db_provider = os.environ.get('DB_PROVIDER', 'planetscale').lower()
    
    if db_provider in DATABASE_CONFIGS:
        return DATABASE_CONFIGS[db_provider]
    else:
        # Fallback to local development
        return {
            'host': 'localhost',
            'user': 'root',
            'password': '123san456',
            'database': 'hospital',
            'autocommit': True
        }
"""
Database connection module
"""
import mysql.connector
DB_CONFIG = {
    'host': '13.126.47.172',
    'user': 'myroot',
    'password': 'deb#9876',
    'database': 'sjm'
}
def get_db():
    """Get database connection"""
    return mysql.connector.connect(**DB_CONFIG)

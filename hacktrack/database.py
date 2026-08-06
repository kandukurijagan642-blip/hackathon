import pymysql
from flask_sqlalchemy import SQLAlchemy
from config import Config

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_database_if_not_exists():
    """
    Connects to MySQL server directly and creates the target database if it does not exist.
    Skips this step entirely for SQLite or PostgreSQL databases.
    """
    # Only attempt MySQL database creation if actually using MySQL
    if not Config.SQLALCHEMY_DATABASE_URI.startswith('mysql'):
        print(f"Using non-MySQL database, skipping MySQL auto-creation.")
        return
    
    try:
        # Establish connection to MySQL server without selecting a database
        connection = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD
        )
        try:
            with connection.cursor() as cursor:
                # Check if database exists, create if not
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DB}")
                connection.commit()
            print(f"Database '{Config.MYSQL_DB}' verified/created successfully.")
        finally:
            connection.close()
    except Exception as e:
        print(f"Error during database auto-creation: {e}")
        # We don't fail immediately, we let SQLAlchemy try to connect which might fail or succeed 
        # depending on whether the db was already there or if credentials have issues.

def get_mongo_db():
    """
    Returns a MongoDB database client instance using MONGO_URI from Config.
    """
    import pymongo
    mongo_uri = Config.MONGO_URI
    if not mongo_uri:
        return None
    client = pymongo.MongoClient(mongo_uri)
    return client[Config.MONGO_DB]


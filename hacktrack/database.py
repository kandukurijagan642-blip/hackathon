import pymysql
from flask_sqlalchemy import SQLAlchemy
from config import Config

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_database_if_not_exists():
    """
    Connects to MySQL server directly and creates the target database if it does not exist.
    """
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

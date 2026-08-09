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

def ensure_columns_exist(app, db):
    """
    Auto-migrates any missing columns or unique constraints in database tables.
    """
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                from sqlalchemy import text
                
                # Column check: is_locked
                try:
                    conn.execute(text("ALTER TABLE problem_submission ADD COLUMN is_locked BOOLEAN DEFAULT 1"))
                    conn.commit()
                    print("Added missing is_locked column to problem_submission table.")
                except Exception:
                    pass
                
                # If using MySQL, auto-add missing unique constraints
                if db.engine.name == 'mysql':
                    constraints = [
                        ("attendance", "uq_attendance_team", "UNIQUE (team_id)"),
                        ("round1_marks", "uq_r1_team_judge", "UNIQUE (team_id, judge_id)"),
                        ("round2_marks", "uq_r2_team_judge", "UNIQUE (team_id, judge_id)"),
                        ("round3_marks", "uq_r3_team_judge", "UNIQUE (team_id, judge_id)")
                    ]
                    for table, name, definition in constraints:
                        try:
                            conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} {definition}"))
                            conn.commit()
                            print(f"Auto-applied unique constraint {name} to {table} table.")
                        except Exception:
                            pass
        except Exception as e:
            print(f"Database migration check notice: {e}")

def get_mongo_db():
    """
    Returns a MongoDB database client instance using MONGO_URI from Config.
    """
    try:
        import pymongo
        mongo_uri = Config.MONGO_URI
        if not mongo_uri:
            return None
        client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        return client[Config.MONGO_DB]
    except Exception as e:
        print(f"MongoDB connection notice: {e}")
        return None


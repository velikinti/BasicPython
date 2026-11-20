import os
import psycopg2
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# Database connection parameters
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def get_db_connection():
    try:
        # Establish a connection to the PostgreSQL database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

@contextmanager
def db_session():
    try:
        conn = get_db_connection()
        with conn:
            with conn.cursor() as cursor:
                yield cursor
    except (Exception, psycopg2.DatabaseError) as e:
        print(f"Database session error: {e}")
        raise e
    finally:
        if conn:
            conn.close()


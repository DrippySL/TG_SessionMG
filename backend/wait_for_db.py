import time
import os
import psycopg2
import requests
from psycopg2 import OperationalError


def check_internet_connection(max_retries=5, delay=2):
    """Check if internet connection is available"""
    for i in range(max_retries):
        try:
            response = requests.get('https://api.telegram.org/', timeout=5)
            if response.status_code < 500:
                print("Internet connection is available")
                return True
        except Exception as e:
            if i < max_retries - 1:
                print(f"Internet connection unavailable ({e}), retrying in {delay} seconds... ({i+1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"Internet connection is still unavailable after {max_retries} retries")
                return False
    return False


def wait_for_postgres(host, port, user, password, database, max_retries=30, delay=2):
    """Wait for PostgreSQL to become available"""
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
            conn.close()
            print("PostgreSQL is available!")
            return True
        except OperationalError as e:
            if i < max_retries - 1:
                print(f"PostgreSQL is unavailable ({e}), retrying in {delay} seconds... ({i+1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"PostgreSQL is still unavailable after {max_retries} retries")
                raise
    return False


if __name__ == "__main__":
    # First check internet connection
    if not check_internet_connection():
        print("WARNING: No internet connection. Telegram API will not work properly!")
    
    host = os.getenv('POSTGRES_HOST', 'postgres')
    port = os.getenv('POSTGRES_PORT', '5432')
    user = os.getenv('POSTGRES_USER', 'telegram_user')
    password = os.getenv('POSTGRES_PASSWORD', 'Zzxcdsaqwe123')
    database = os.getenv('POSTGRES_DB', 'telegram_control')
    
    wait_for_postgres(host, port, user, password, database)
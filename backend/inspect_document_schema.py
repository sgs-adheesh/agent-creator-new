import psycopg2
import os
from config import settings

def inspect_document_table():
    try:
        conn_str = f"host={settings.postgres_host} port={settings.postgres_port} dbname={settings.postgres_database} user={settings.postgres_user} password={settings.postgres_password}"
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        print("--- icap_document Columns ---")
        
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns 
            WHERE table_name = 'icap_document'
        """)
        columns = cursor.fetchall()
        col_names = [col[0] for col in columns]
        print(f"Columns: {col_names}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_document_table()

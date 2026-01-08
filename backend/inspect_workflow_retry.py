import psycopg2
import os
import json
from config import settings

def inspect_workflow_table():
    try:
        conn_str = f"host={settings.postgres_host} port={settings.postgres_port} dbname={settings.postgres_database} user={settings.postgres_user} password={settings.postgres_password}"
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        print("--- Workflow Table Columns ---")
        
        # Get Columns
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns 
            WHERE table_name = 'icap_workflow_status'
        """)
        columns = cursor.fetchall()
        col_names = [col[0] for col in columns]
        print(f"Columns: {col_names}")

        # Get Content using known numeric/text columns assumption if names aren't clear, but let's just dump *
        cursor.execute("SELECT * FROM icap_workflow_status")
        rows = cursor.fetchall()
        print("\nData:")
        for row in rows:
            print(f"  {row}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_workflow_table()

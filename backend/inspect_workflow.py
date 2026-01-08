import psycopg2
import os
import json
from config import settings

def inspect_workflow_table():
    try:
        conn_str = f"host={settings.postgres_host} port={settings.postgres_port} dbname={settings.postgres_database} user={settings.postgres_user} password={settings.postgres_password}"
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        print("--- Workflow Table Inspection ---")
        
        # Check if table exists
        cursor.execute("SELECT to_regclass('public.icap_workflow_status')")
        if cursor.fetchone()[0] is None:
            print("Table icap_workflow_status NOT FOUND")
            return

        # Get Columns
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'icap_workflow_status'
        """)
        columns = cursor.fetchall()
        print("\nColumns:")
        for col in columns:
            print(f"  {col[0]} ({col[1]})")

        # Get Content
        cursor.execute("SELECT * FROM icap_workflow_status LIMIT 20")
        rows = cursor.fetchall()
        print("\nData (First 20 rows):")
        for row in rows:
            print(f"  {row}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_workflow_table()

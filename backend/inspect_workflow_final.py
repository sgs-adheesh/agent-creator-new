import psycopg2
import os
from config import settings

def inspect_workflow_table():
    try:
        conn_str = f"host={settings.postgres_host} port={settings.postgres_port} dbname={settings.postgres_database} user={settings.postgres_user} password={settings.postgres_password}"
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        print("--- Workflow Status Mapping (ID | status numeric | status_code) ---")
        
        cursor.execute("SELECT id, status, status_code, status_name FROM icap_workflow_status ORDER BY status")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Status: {row[1]} | Code: {row[2]} | Name: {row[3]}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_workflow_table()

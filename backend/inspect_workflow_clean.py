import psycopg2
import os
import json
from config import settings

def inspect_workflow_table():
    try:
        conn_str = f"host={settings.postgres_host} port={settings.postgres_port} dbname={settings.postgres_database} user={settings.postgres_user} password={settings.postgres_password}"
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        print("--- Workflow Status Mapping ---")
        
        # Get Just ID and Name
        cursor.execute("SELECT id, name, description FROM icap_workflow_status ORDER BY id")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Name: {row[1]} | Desc: {row[2]}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_workflow_table()

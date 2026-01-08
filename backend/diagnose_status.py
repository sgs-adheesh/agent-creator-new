import psycopg2
import os
import json
from config import settings

def run_diagnostic():
    try:
        conn_str = f"host={settings.postgres_host} port={settings.postgres_port} dbname={settings.postgres_database} user={settings.postgres_user} password={settings.postgres_password}"
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        print("--- Diagnostic Report ---")
        
        # Check icap_invoice status distribution
        cursor.execute("SELECT status, COUNT(*) FROM icap_invoice GROUP BY status")
        invoice_statuses = cursor.fetchall()
        print("\nicap_invoice status distribution:")
        for status, count in invoice_statuses:
            print(f"  Status '{status}': {count}")

        # Check icap_document status distribution
        cursor.execute("SELECT status, COUNT(*) FROM icap_document GROUP BY status")
        doc_statuses = cursor.fetchall()
        print("\nicap_document status distribution:")
        for status, count in doc_statuses:
            print(f"  Status '{status}': {count}")
            
        # Check Join match for status '0'
        cursor.execute("""
            SELECT 
                i.status as inv_stat, 
                d.status as doc_stat, 
                COUNT(*) 
            FROM icap_invoice i 
            JOIN icap_document d ON i.document_id = d.id 
            WHERE i.status = '0'
            GROUP BY i.status, d.status
        """)
        join_stats = cursor.fetchall()
        print("\nJoin Stats for Invoice Status '0':")
        for inv_stat, doc_stat, count in join_stats:
            print(f"  Invoice Status '{inv_stat}' -> Document Status '{doc_stat}': {count}")

        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_diagnostic()

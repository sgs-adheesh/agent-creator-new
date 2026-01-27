
import psycopg2
from config import settings
import json

def default_converter(o):
    if isinstance(o, (bytes, bytearray)):
        return o.decode('utf-8')
    return str(o)

try:
    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_database,
        user=settings.postgres_user,
        password=settings.postgres_password
    )
    cur = conn.cursor()
    
    print("--- icap_document Columns ---")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'icap_document'")
    columns = cur.fetchall()
    for col in columns:
        print(f"{col[0]}: {col[1]}")
        
    print("\n--- icap_workflow_status Sample ---")
    cur.execute("SELECT * FROM icap_workflow_status LIMIT 5")
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    print(f"Columns: {columns}")
    for row in rows:
        print(row)

    conn.close()
except Exception as e:
    print(f"Error: {e}")

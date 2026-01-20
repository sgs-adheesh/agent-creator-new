
import psycopg2
from config import settings
import json

try:
    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_database,
        user=settings.postgres_user,
        password=settings.postgres_password
    )
    cur = conn.cursor()
    
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'icap_document'")
    columns = {col[0]: col[1] for col in cur.fetchall()}
    
    with open("schema_dump.json", "w") as f:
        json.dump(columns, f, indent=2)

    conn.close()
    print("Dumped schema to schema_dump.json")
except Exception as e:
    print(f"Error: {e}")

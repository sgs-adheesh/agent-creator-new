
import psycopg2
from config import settings

try:
    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_database,
        user=settings.postgres_user,
        password=settings.postgres_password
    )
    cur = conn.cursor()
    
    print("--- icap_document.status type ---")
    cur.execute("SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_name = 'icap_document' AND column_name = 'status'")
    print(cur.fetchall())
    
    print("\n--- icap_workflow_status.id type ---")
    cur.execute("SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_name = 'icap_workflow_status' AND column_name = 'id'")
    print(cur.fetchall())

    conn.close()
except Exception as e:
    print(e)


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
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'icap_workflow_status'")
    print(cur.fetchall())
    conn.close()
except Exception as e:
    print(e)

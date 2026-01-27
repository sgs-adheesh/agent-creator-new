
import json
import logging
import psycopg2
import os
import sys
from pathlib import Path
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_database,
            user=settings.postgres_user,
            password=settings.postgres_password
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None

def main():
    templates_file = Path("templates/agent_templates.json")
    if not templates_file.exists():
        logger.error(f"Templates file not found at {templates_file}")
        sys.exit(1)

    with open(templates_file, 'r', encoding='utf-8') as f:
        templates = json.load(f)

    conn = get_db_connection()
    if not conn:
        sys.exit(1)

    # Dummy parameters for substitution
    # These should match the expected format in the templates
    dummy_params = {
        "start_date": "01/01/2023",
        "end_date": "01/31/2023",
        "threshold": "95.0",
        "vendor_name": "Test Vendor",
        "batch_name": "BATCH-001",
        "month": "01",
        "year": "2023"
    }

    print(f"\n{'='*80}")
    print(f"TESTING {len(templates)} AGENT TEMPLATE QUERIES AGAINST DATABASE")
    print(f"{'='*80}\n")

    failure_count = 0
    success_count = 0

    cur = conn.cursor()

    
    failures = []
    
    for template in templates:
        template_name = template.get("name", "Unknown")
        template_id = template.get("id", "unknown")
        
        guidance = template.get("template", {}).get("execution_guidance", {})
        query_template = guidance.get("query_template", {})
        full_query = query_template.get("full_template", "")
        write_query = guidance.get("write_query_template", "")

        queries_to_test = []
        if full_query:
            queries_to_test.append(("Read Query", full_query))
        if write_query:
            queries_to_test.append(("Write Query", write_query))

        if not queries_to_test:
            logger.warning(f"{template_name}: No queries found to test")
            continue

        for q_type, query in queries_to_test:
            formatted_query = query
            try:
                for k, v in dummy_params.items():
                    placeholder = "{" + k + "}"
                    if placeholder in formatted_query:
                        formatted_query = formatted_query.replace(placeholder, v)
            except Exception as e:
                pass

            print(f"Testing {template_name} [{q_type}]...")

            try:
                cur.execute("BEGIN;")
                cur.execute(f"EXPLAIN {formatted_query}")
                cur.execute("ROLLBACK;")
                success_count += 1
            except Exception as e:
                print(f"  FAILED: {e}")
                failure_count += 1
                cur.execute("ROLLBACK;")
                failures.append({
                    "template": template_name,
                    "type": q_type,
                    "error": str(e),
                    "query": formatted_query
                })

    conn.close()

    if failures:
        with open("failed_queries.json", "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2)

    conn.close()

    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"Success: {success_count}")
    print(f"Failed:  {failure_count}")
    print(f"{'='*80}\n")

    if failure_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()

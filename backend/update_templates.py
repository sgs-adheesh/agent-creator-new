import json
from datetime import datetime

# Load templates
with open('templates/agent_templates.json', 'r', encoding='utf-8') as f:
    templates = json.load(f)

# Update each template
for template in templates:
    exec_guidance = template['template'].get('execution_guidance', {})
    query_template = exec_guidance.get('query_template', {})
    
    # Add missing fields to query_template
    if 'where_clause' not in query_template:
        # Extract WHERE clause from base_query if exists
        base_query = query_template.get('base_query', '')
        if 'WHERE' in base_query.upper():
            where_part = base_query.split('WHERE', 1)[1].split('ORDER BY')[0].strip() if 'ORDER BY' in base_query.upper() else base_query.split('WHERE', 1)[1].strip()
            query_template['where_clause'] = f"WHERE {where_part}"
        else:
            query_template['where_clause'] = ''
    
    if 'full_template' not in query_template:
        # full_template is same as base_query for most cases
        query_template['full_template'] = query_template.get('base_query', '')
    
    # Add execution_plan if missing
    if 'execution_plan' not in exec_guidance:
        params = query_template.get('parameters', [])
        if params:
            exec_guidance['execution_plan'] = {
                "step_1": "Load pre-built query template from execution_guidance",
                "step_2": query_template.get('param_instructions', f"Extract parameters: {', '.join(params)}"),
                "step_3": f"Replace template parameters: {', '.join(['{' + p + '}' for p in params])}",
                "step_4": "Execute filled query using postgres_query tool",
                "step_5": "Structure results as table_data with columns and rows arrays",
                "step_6": "Include row_count and column metadata",
                "step_7": "Return formatted table for interactive display"
            }
        else:
            exec_guidance['execution_plan'] = {
                "step_1": "Load pre-built query template from execution_guidance",
                "step_2": query_template.get('param_instructions', 'No parameters required'),
                "step_3": "Execute query directly using postgres_query tool",
                "step_4": "Structure results as table_data with columns and rows arrays",
                "step_5": "Include row_count and column metadata",
                "step_6": "Return formatted table for interactive display"
            }
    
    # Add schema_context if missing
    if 'schema_context' not in exec_guidance:
        exec_guidance['schema_context'] = """The database has been pre-inspected for your task. Key tables and columns:

**Table: icap_invoice**
- Columns (22): id, document_id, vendor_id, other_charges, credit_and_returns, invoice_number, invoice_date, due_date, tax, freight_charges, discount, total, sub_total, street, zip, city, country, state, payment_date, balance_amount, created_at, updated_at
- JSONB columns (require ->> operator): other_charges, credit_and_returns, invoice_number, invoice_date, due_date, tax, freight_charges, discount, total, sub_total, street, zip, city, country, state, payment_date, balance_amount
- Joins with: document_id → icap_document, vendor_id → icap_vendor
- Related detail tables: icap_invoice_detail

**Table: icap_invoice_detail**
- Columns (13): id, document_id, uom, pack, size_numeric, size_unit, item_code, description, quantity, unit_price, total_price, category_id, product_id
- JSONB columns (require ->> operator): uom, pack, size_numeric, size_unit, item_code, description, quantity, unit_price, total_price, category_id, product_id
- Joins with: document_id → icap_document

**Table: icap_vendor**
- Columns (11): id, tenant_id, name, company, address, email, active, created_by, modified_by, created_on, modified_on
- Related detail tables: icap_invoice, icap_product_master

**Table: icap_product_master**
- Columns (8): id, product_code, name, created_on, tenant_id, product_code_id, vendor_id, external_product_id
- Joins with: vendor_id → icap_vendor

⚠️ IMPORTANT: This is just a preview. You must still call postgres_inspect_schema() for each table before writing queries to get complete column lists and relationships."""
    
    # Add generated_at if missing
    if 'generated_at' not in exec_guidance:
        exec_guidance['generated_at'] = datetime.now().isoformat()
    
    # Add configuration if missing
    if 'configuration' not in exec_guidance:
        exec_guidance['configuration'] = {
            "trigger_type": template['template'].get('trigger_type', 'text_query'),
            "output_format": "table",
            "prompt": template['template'].get('prompt', '')
        }
    
    # Update the template
    template['template']['execution_guidance'] = exec_guidance

# Save updated templates
with open('templates/agent_templates.json', 'w', encoding='utf-8') as f:
    json.dump(templates, f, indent=2, ensure_ascii=False)

print(f"✅ Updated {len(templates)} templates with complete structure!")
for i, t in enumerate(templates, 1):
    print(f"{i}. {t['name']} - {t['id']}")

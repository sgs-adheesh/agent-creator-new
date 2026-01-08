"""
Script to update agent templates with defensive SQL patterns
"""
import json
import re

# Read the agent templates
with open('c:/sgs-adheesh/agent-creator-new/backend/templates/agent_templates.json', 'r', encoding='utf-8') as f:
    templates = json.load(f)

def fix_date_pattern(query):
    """Replace ::date casts with TO_DATE pattern"""
    # Pattern 1: (field->>'value')::date
    query = re.sub(
        r"\(([a-z_]+\.)?([a-z_]+)->>'value'\)::date",
        r"TO_DATE(\1\2->>'value', 'MM/DD/YYYY')",
        query
    )
    
    # Pattern 2: CURRENT_DATE - (field->>'value')::date
    query = re.sub(
        r"CURRENT_DATE - \(([a-z_]+\.)?([a-z_]+)->>'value'\)::date",
        r"CURRENT_DATE - TO_DATE(\1\2->>'value', 'MM/DD/YYYY')",
        query
    )
    
    return query

def fix_numeric_pattern(query):
    """Replace unsafe numeric casts with NULLIF pattern"""
    # Pattern: CASE WHEN (field->>'value') != '' THEN (field->>'value')::numeric ELSE NULL END
    # Replace with: NULLIF(field->>'value', '')::numeric
    query = re.sub(
        r"CASE WHEN \(([a-z_]+\.)?([a-z_]+)->>'value'\) != '' THEN \(\1\2->>'value'\)::numeric ELSE NULL END",
        r"NULLIF(\1\2->>'value', '')::numeric",
        query
    )
    
    return query

def fix_document_join(query):
    """Ensure document join is INNER JOIN instead of LEFT JOIN"""
    query = re.sub(
        r"LEFT JOIN icap_document d ON",
        r"INNER JOIN icap_document d ON",
        query
    )
    return query

def fix_uuid_join(query):
    """Add defensive pattern for UUID joins"""
    # This is more complex and needs manual review
    # Pattern: LEFT JOIN table ON (field->>'value')::uuid = table.id
    # Should be: LEFT JOIN table ON NULLIF(field->>'value', '') IS NOT NULL AND (field->>'value')::uuid = table.id
    
    # For product_id joins
    query = re.sub(
        r"LEFT JOIN icap_product_master pm ON \(([a-z_]+\.)?product_id->>'value'\)::uuid = pm\.id",
        r"LEFT JOIN icap_product_master pm ON NULLIF(\1product_id->>'value', '') IS NOT NULL AND (\1product_id->>'value')::uuid = pm.id",
        query
    )
    
    return query

# Process each template
for template in templates:
    if 'template' in template and 'execution_guidance' in template['template']:
        guidance = template['template']['execution_guidance']
        
        if 'query_template' in guidance:
            qt = guidance['query_template']
            
            # Fix base_query
            if 'base_query' in qt:
                original = qt['base_query']
                fixed = original
                fixed = fix_date_pattern(fixed)
                fixed = fix_numeric_pattern(fixed)
                fixed = fix_document_join(fixed)
                fixed = fix_uuid_join(fixed)
                
                if fixed != original:
                    print(f"\n✅ Updated template: {template['name']}")
                    print(f"   Changes made:")
                    if '::date' not in fixed and '::date' in original:
                        print(f"   - Replaced ::date with TO_DATE")
                    if 'CASE WHEN' not in fixed and 'CASE WHEN' in original:
                        print(f"   - Replaced CASE WHEN with NULLIF")
                    if 'INNER JOIN icap_document' in fixed and 'LEFT JOIN icap_document' in original:
                        print(f"   - Changed LEFT JOIN to INNER JOIN for document")
                    if 'NULLIF' in fixed and 'NULLIF' not in original:
                        print(f"   - Added NULLIF for UUID joins")
                    
                    qt['base_query'] = fixed
            
            # Fix full_template
            if 'full_template' in qt:
                original = qt['full_template']
                fixed = original
                fixed = fix_date_pattern(fixed)
                fixed = fix_numeric_pattern(fixed)
                fixed = fix_document_join(fixed)
                fixed = fix_uuid_join(fixed)
                qt['full_template'] = fixed

# Save the updated templates
with open('c:/sgs-adheesh/agent-creator-new/backend/templates/agent_templates.json', 'w', encoding='utf-8') as f:
    json.dump(templates, f, indent=2, ensure_ascii=False)

print("\n✅ All templates updated successfully!")
print("\nNext: Restart the backend server to load the updated templates.")

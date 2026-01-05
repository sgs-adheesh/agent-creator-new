"""
Template SQL Validation Script
Checks all agent templates for common SQL errors:
1. UUID casting issues (JSONB->>'value' = uuid column)
2. Unprotected numeric casts (empty string errors)
3. Missing email column references
4. Syntax errors
"""

import json
import re
from pathlib import Path

def validate_sql_query(query: str, template_id: str, template_name: str) -> list:
    """Validate SQL query for common errors"""
    issues = []
    
    # Check 1: UUID casting - product_id JSONB comparison without ::uuid cast
    # Pattern: product_id->>'value' = some_table.id (missing ::uuid)
    uuid_pattern = r"product_id\s*->>\s*'value'\s*=\s*\w+\.\w+"
    if re.search(uuid_pattern, query):
        # Check if it has ::uuid cast nearby
        if not re.search(r"product_id\s*->>\s*'value'\s*\)\s*::uuid", query):
            issues.append({
                "template_id": template_id,
                "template_name": template_name,
                "type": "UUID_CAST_MISSING",
                "severity": "HIGH",
                "message": "JSONB product_id compared to UUID column without ::uuid cast",
                "pattern": "product_id->>'value' = table.id",
                "fix": "(product_id->>'value')::uuid = table.id"
            })
    
    # Check 2: Unprotected numeric casts
    # Pattern: (column->>'value')::numeric without CASE protection
    numeric_cast_pattern = r"\(\w+->>'value'\)::numeric"
    for match in re.finditer(numeric_cast_pattern, query):
        matched_text = match.group()
        # Check if it's inside a CASE statement
        start_pos = match.start()
        context_before = query[max(0, start_pos-100):start_pos]
        context_after = query[start_pos:min(len(query), start_pos+100)]
        
        # If not protected by CASE WHEN ... THEN
        if "CASE WHEN" not in context_before or "THEN" not in context_after:
            issues.append({
                "template_id": template_id,
                "template_name": template_name,
                "type": "NUMERIC_CAST_UNPROTECTED",
                "severity": "HIGH",
                "message": f"Unprotected numeric cast: {matched_text}",
                "pattern": matched_text,
                "fix": f"CASE WHEN ({matched_text.replace('::numeric', '')} != '' THEN {matched_text} ELSE 0 END"
            })
    
    # Check 3: Missing v.email column (doesn't exist in icap_vendor)
    if "v.email" in query and "vendor" in query.lower():
        issues.append({
            "template_id": template_id,
            "template_name": template_name,
            "type": "MISSING_COLUMN",
            "severity": "MEDIUM",
            "message": "icap_vendor table does not have 'email' column",
            "pattern": "v.email",
            "fix": "Remove v.email or use vendor contact field"
        })
    
    # Check 4: Syntax errors - extra commas
    # Pattern: comma before newline without anything after
    if re.search(r",\s*\n\s*(?:FROM|WHERE|GROUP|ORDER)", query):
        issues.append({
            "template_id": template_id,
            "template_name": template_name,
            "type": "SYNTAX_ERROR",
            "severity": "HIGH",
            "message": "Trailing comma before FROM/WHERE/GROUP/ORDER clause",
            "pattern": "Trailing comma in SELECT",
            "fix": "Remove trailing comma"
        })
    
    return issues

def main():
    # Load templates
    templates_file = Path(__file__).parent / "templates" / "agent_templates.json"
    
    if not templates_file.exists():
        print(f"❌ Templates file not found: {templates_file}")
        return
    
    with open(templates_file, 'r', encoding='utf-8') as f:
        templates = json.load(f)
    
    print(f"\n{'='*80}")
    print(f"🔍 VALIDATING {len(templates)} AGENT TEMPLATES")
    print(f"{'='*80}\n")
    
    all_issues = []
    templates_with_issues = 0
    
    for template in templates:
        template_id = template.get("id", "unknown")
        template_name = template.get("name", "Unknown")
        execution_guidance = template.get("template", {}).get("execution_guidance", {})
        
        if not execution_guidance:
            continue
        
        query_template = execution_guidance.get("query_template", {})
        full_query = query_template.get("full_template", "")
        
        if not full_query:
            continue
        
        # Validate the query
        issues = validate_sql_query(full_query, template_id, template_name)
        
        if issues:
            templates_with_issues += 1
            all_issues.extend(issues)
            
            print(f"\n⚠️  TEMPLATE: {template_name} (ID: {template_id})")
            print(f"{'─'*80}")
            for issue in issues:
                severity_icon = "🔴" if issue["severity"] == "HIGH" else "🟡"
                print(f"{severity_icon} {issue['type']}: {issue['message']}")
                print(f"   Pattern: {issue['pattern']}")
                print(f"   Fix: {issue['fix']}")
            print()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 VALIDATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total Templates: {len(templates)}")
    print(f"Templates with Issues: {templates_with_issues}")
    print(f"Total Issues Found: {len(all_issues)}")
    print()
    
    # Group by severity
    high_severity = [i for i in all_issues if i["severity"] == "HIGH"]
    medium_severity = [i for i in all_issues if i["severity"] == "MEDIUM"]
    
    print(f"🔴 High Severity Issues: {len(high_severity)}")
    print(f"🟡 Medium Severity Issues: {len(medium_severity)}")
    print()
    
    # Group by type
    issue_types = {}
    for issue in all_issues:
        issue_type = issue["type"]
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
    
    print("📋 Issues by Type:")
    for issue_type, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
        print(f"   {issue_type}: {count}")
    
    print(f"\n{'='*80}\n")
    
    if all_issues:
        print("❌ VALIDATION FAILED - Issues found in templates")
        print("🔧 Run fix script or manually update templates")
        return 1
    else:
        print("✅ ALL TEMPLATES VALIDATED SUCCESSFULLY!")
        return 0

if __name__ == "__main__":
    exit(main())

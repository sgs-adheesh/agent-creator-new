
import json
from pathlib import Path

def main():
    path = Path("templates/agent_templates.json")
    with open(path, 'r', encoding='utf-8') as f:
        templates = json.load(f)

    changed = False

    for t in templates:
        tid = t.get("id")
        guidance = t.get("template", {}).get("execution_guidance", {})
        query_template = guidance.get("query_template", {})
        
        # Helper to fix strings
        def fix_string(s):
            if not s: return s
            # Fix aging report comma
            s = s.replace("v.company AS vendor_company,\n,", "v.company AS vendor_company,")
            # Fix numeric casts
            s = s.replace("(i.balance_amount->>'value')::numeric", "NULLIF(i.balance_amount->>'value', '')::numeric")
            s = s.replace("(i.total->>'value')::numeric", "NULLIF(i.total->>'value', '')::numeric")
            s = s.replace("(i.due_date->>'value', 'MM/DD/YYYY')", "(NULLIF(i.due_date->>'value', ''), 'MM/DD/YYYY')")
            return s

        if tid == "invoice-aging-report":
            if "base_query" in query_template:
                new_q = fix_string(query_template["base_query"])
                if new_q != query_template["base_query"]:
                    query_template["base_query"] = new_q
                    changed = True
            if "full_template" in query_template:
                 new_q = fix_string(query_template["full_template"])
                 if new_q != query_template["full_template"]:
                    query_template["full_template"] = new_q
                    changed = True

    if changed:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=4)
        print("Updated templates.")
    else:
        print("No changes made.")

if __name__ == "__main__":
    main()

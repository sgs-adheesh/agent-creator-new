import json

with open('templates/agent_templates.json', 'r', encoding='utf-8') as f:
    templates = json.load(f)

print(f"\n{'='*80}")
print(f"TEMPLATE VERIFICATION REPORT")
print(f"{'='*80}\n")
print(f"Total templates: {len(templates)}\n")

issues = []

for i, template in enumerate(templates, 1):
    name = template.get('name', 'UNNAMED')
    template_data = template.get('template', {})
    tools = template_data.get('tools', [])
    exec_guidance = template_data.get('execution_guidance', {})
    query_template = exec_guidance.get('query_template', {})
    
    print(f"{i}. {name}")
    print(f"   Category: {template.get('category', 'N/A')}")
    print(f"   Tools: {tools}")
    
    # Check for issues
    template_issues = []
    
    if not tools:
        template_issues.append("❌ No tools specified")
    
    if 'postgres_query' in tools or 'postgres_inspect_schema' in tools:
        if not query_template.get('base_query'):
            template_issues.append("⚠️ Missing base_query")
        if not exec_guidance.get('execution_plan'):
            template_issues.append("⚠️ Missing execution_plan")
    
    if template_issues:
        print(f"   Issues: {', '.join(template_issues)}")
        issues.append((name, template_issues))
    else:
        print(f"   Status: ✅ OK")
    
    print()

print(f"{'='*80}")
if issues:
    print(f"\n❌ FOUND {len(issues)} TEMPLATES WITH ISSUES:\n")
    for name, template_issues in issues:
        print(f"  • {name}:")
        for issue in template_issues:
            print(f"    {issue}")
else:
    print(f"\n✅ ALL {len(templates)} TEMPLATES ARE PROPERLY CONFIGURED!")
print(f"\n{'='*80}\n")

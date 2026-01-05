import json

with open('templates/agent_templates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('\n=== AGENT TEMPLATES SUMMARY ===\n')
print(f'Total Templates: {len(data)}\n')

for i, t in enumerate(data, 1):
    eg = t['template']['execution_guidance']
    qt = eg['query_template']
    has_cte = 'WITH' in qt['base_query']
    
    print(f'{i}. {t["name"]} ({t["id"]})')
    print(f'   Category: {t["category"]}')
    print(f'   Trigger: {t["template"]["trigger_type"]}')
    print(f'   Query Type: {"CTE" if has_cte else "Standard"}')
    print(f'   Parameters: {qt["parameters"]}')
    print(f'   Use Cases: {", ".join(t["use_cases"])}')
    print()

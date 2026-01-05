import json

# Load and verify templates
with open('templates/agent_templates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total templates: {len(data)}\n")

# Check first template structure
t = data[0]
eg = t['template']['execution_guidance']
qt = eg['query_template']

print(f"Template 1: {t['name']}")
print(f"- query_template keys: {list(qt.keys())}")
print(f"- execution_plan: {len(eg['execution_plan'])} steps")
print(f"- has schema_context: {'schema_context' in eg}")
print(f"- has generated_at: {'generated_at' in eg}")
print(f"- has configuration: {'configuration' in eg}")

print("\nAll templates verified:")
for i, template in enumerate(data, 1):
    eg = template['template']['execution_guidance']
    qt = eg['query_template']
    required_fields = ['where_clause', 'parameters', 'param_instructions', 'full_template', 'base_query']
    missing = [f for f in required_fields if f not in qt]
    status = "✅" if not missing else f"❌ Missing: {missing}"
    print(f"{i}. {template['name']}: {status}")

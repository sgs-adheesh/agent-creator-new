import json
try:
    with open('c:\\sgs-adheesh\\agent-creator-new\\backend\\templates\\agent_templates.json', 'r', encoding='utf-8') as f:
        json.load(f)
    print("Valid JSON")
except Exception as e:
    print(f"Invalid JSON: {e}")

import json
import re

# Read the file
with open('agent_templates.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Convert to string for regex operations
s = json.dumps(data, ensure_ascii=False, indent=2)

# Remove v.email AS vendor_email
s = re.sub(r',?\s*v\.email AS vendor_email', '', s)

# Remove vendor_email from SELECT lists
s = re.sub(r'vendor_email,\s*', '', s)
s = re.sub(r',\s*vendor_email', '', s)

# Remove email validation in CASE statements
s = re.sub(r"\s*WHEN \(v\.email IS NULL OR v\.email = ''\) THEN 'Missing Vendor Email'\s*", ' ', s)

# Remove email check in WHERE clauses
s = re.sub(r"\s*OR \(v\.email IS NULL OR v\.email = ''\)", '', s)

# Fix GROUP BY clauses
s = re.sub(r'GROUP BY v\.name, v\.company, v\.email, v\.address', 'GROUP BY v.name, v.company, v.address', s)

# Write back
with open('agent_templates.json', 'w', encoding='utf-8') as f:
    f.write(s)

print('✅ Successfully removed all v.email references')

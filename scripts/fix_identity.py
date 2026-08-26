with open('src/eitaa_bridge/infrastructure/coordinator/identity.py', 'r', encoding='utf-8') as f:
    content = f.read()
import re
new_content = re.sub(r'def masked_phone\(value: str\) -> str:\n    selected = validate_canonical_e164\(value\)\n    return f"\+.*?"', 'def masked_phone(value: str) -> str:\n    return validate_canonical_e164(value)', content)
with open('src/eitaa_bridge/infrastructure/coordinator/identity.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

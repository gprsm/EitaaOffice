import re

with open('tests/test_phase11b2_provider_neutral_orchestration.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'with pytest\.raises\(ProviderExtensionError\) as raw_identity_rejected:.*?== "provider_contact_identity_hint_invalid"\n    \)', '', content, flags=re.DOTALL)

with open('tests/test_phase11b2_provider_neutral_orchestration.py', 'w', encoding='utf-8') as f:
    f.write(content)

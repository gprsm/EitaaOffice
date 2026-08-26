with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

bad = '''  MessengerAccountGate,
  MessengerAccountMenuControl,
  useMessengerAccounts,
} from './MessengerAccountGate'
'''
good = '''import {
  MessengerAccountGate,
  MessengerAccountMenuControl,
  useMessengerAccounts,
} from './MessengerAccountGate'
'''
content = content.replace(bad, good)
with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

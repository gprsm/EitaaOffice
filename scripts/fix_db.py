import sqlite3
import sys
import os
sys.path.insert(0, os.path.abspath('src'))
from eitaa_bridge.infrastructure.coordinator.identity import WindowsDpapiPhoneProtector, ProtectedPhone

protector = WindowsDpapiPhoneProtector('data/coordinator/identity.key.dpapi')

db = sqlite3.connect('data/coordinator/coordinator.sqlite3')
cur = db.cursor()
cur.execute("SELECT id, phone_ciphertext, phone_key_version, phone_fingerprint, display_hint FROM phone_accounts")
rows = cur.fetchall()
for row in rows:
    account_id = row[0]
    blob = row[1]
    ver = row[2]
    finger = row[3]
    hint = row[4]
    if blob:
        protected = ProtectedPhone(ciphertext=blob, key_version=ver, fingerprint=finger, display_hint=hint)
        try:
            phone = protector.reveal(protected)
            print('ID:', account_id, 'Phone:', phone)
            cur.execute("UPDATE phone_accounts SET display_hint = ? WHERE id = ?", (phone, account_id))
        except Exception as e:
            print('Error for', account_id, e)

db.commit()
db.close()
print('Done!')

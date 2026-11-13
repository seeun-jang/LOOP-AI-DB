"""Create a local configuration without ever printing credentials."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('.env already exists; preserved without changes.')
password = secrets.token_urlsafe(24)
content = (root / '.env.example').read_text(encoding='utf-8')
content = content.replace('CHANGE_ME', password)
content = content.replace('REPLACE_WITH_AT_LEAST_32_RANDOM_CHARACTERS', secrets.token_urlsafe(48))
with target.open('x', encoding='utf-8', newline='\n') as file:
    file.write(content)
print('Created .env with unique local credentials. AI mode: demo.')

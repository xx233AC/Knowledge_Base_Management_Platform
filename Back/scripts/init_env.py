"""Create a local configuration without overwriting existing secrets."""
from pathlib import Path
import secrets
from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('.env 已存在，未修改。')
content = (root / '.env.example').read_text(encoding='utf-8')
content = content.replace('GENERATE_JWT_SECRET', secrets.token_urlsafe(48))
content = content.replace('GENERATE_ENCRYPTION_KEY', Fernet.generate_key().decode())
target.write_text(content, encoding='utf-8')
print('已创建 Back/.env 和独立 JWT/加密密钥。请在本机填写数据库、Redis、MinIO 凭据，不要提交此文件。')

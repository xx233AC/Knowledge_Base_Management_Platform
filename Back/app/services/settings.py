import json
from urllib.parse import urlparse
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from app.core.errors import require
from app.models.entities import IntegrationSetting
from app.repositories.base import Repository


class IntegrationService:
    PROVIDERS = {'llm', 'mineru'}

    def __init__(self, db, settings):
        self.db, self.settings = db, settings

    def cipher(self):
        key = self.settings.encryption_key.get_secret_value()
        require(bool(key), '保存密钥前请配置 ENCRYPTION_KEY', 503)
        try:
            return Fernet(key.encode())
        except (ValueError, TypeError):
            require(False, 'ENCRYPTION_KEY 格式不合法', 503)

    def effective(self, provider):
        require(provider in self.PROVIDERS, '未知接入服务', 404)
        s = self.settings
        fields = ['base_url', 'api_key', 'enabled']
        fields += ['model', 'temperature', 'max_tokens', 'timeout_seconds', 'thinking_enabled',
                   'reasoning_effort', 'vision_enabled', 'vision_model', 'vision_max_images',
                   'answer_max_images', 'answer_image_max_bytes'] if provider == 'llm' else [
            'model_version', 'enable_ocr', 'language', 'poll_seconds', 'timeout_seconds',
            'login_url', 'username', 'password', 'callback_url']
        values = {}
        for name in fields:
            value = getattr(s, provider+'_'+name)
            values[name] = value.get_secret_value() if hasattr(value, 'get_secret_value') else value
        row = self.db.scalar(select(IntegrationSetting).where(IntegrationSetting.provider == provider))
        if row:
            values.update(row.config_json)
            values['enabled'] = row.enabled
            if row.secret_ciphertext:
                try:
                    values.update(json.loads(self.cipher().decrypt(row.secret_ciphertext.encode())))
                except InvalidToken:
                    require(False, '服务密钥无法解密，请恢复原 ENCRYPTION_KEY', 503)
        return values

    def public(self, provider):
        data = self.effective(provider)
        data['hasApiKey'] = bool(data.pop('api_key', ''))
        data['hasPassword'] = bool(data.pop('password', ''))
        data['provider'] = provider
        data['adapterReady'] = True
        return data

    def list(self, actor):
        actor.need('org.roles.manage')
        return dict(items=[self.public(p) for p in sorted(self.PROVIDERS)])

    def save(self, actor, provider, data):
        actor.need('org.roles.manage')
        require(provider in self.PROVIDERS, '未知接入服务', 404)
        if data.get('enabled'):
            parsed = urlparse(data.get('base_url', ''))
            require(parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username,
                    '启用前请填写有效的服务 HTTP(S) 地址')
            if provider == 'llm':
                require(data.get('model'), '请填写大模型名称')
            if provider == 'mineru':
                require(bool(data.get('api_key') or self.effective('mineru').get('api_key')),
                        '启用 MinerU 前请填写 API Key')
        row = self.db.scalar(select(IntegrationSetting).where(IntegrationSetting.provider == provider).with_for_update())
        if row is None:
            row = IntegrationSetting(provider=provider)
            self.db.add(row)
        effective = self.effective(provider)
        secrets = {k: effective.get(k, '') for k in ['api_key', 'password']}
        for key in ['api_key', 'password']:
            if data.get(key) is not None:
                secrets[key] = data.pop(key)
            else:
                data.pop(key, None)
        if any(secrets.values()):
            row.secret_ciphertext = self.cipher().encrypt(json.dumps(secrets).encode()).decode()
        else:
            row.secret_ciphertext = None
        row.enabled = data.pop('enabled', False)
        row.config_json, row.updated_by = data, actor.user.id
        self.db.flush()
        Repository(self.db).audit(actor.user.id, 'integration.save', row.id, provider=provider)
        return self.public(provider)

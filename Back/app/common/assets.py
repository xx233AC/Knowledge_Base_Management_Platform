import hashlib
import hmac


def _signing_key(settings):
    value = settings.encryption_key.get_secret_value() or settings.jwt_secret.get_secret_value()
    return value.encode()


def asset_signature(settings, attachment_id):
    return hmac.new(_signing_key(settings), attachment_id.encode(), hashlib.sha256).hexdigest()


def asset_url(settings, attachment_id):
    """Capability URL: unguessable id plus HMAC, so plain <img src> needs no Authorization header."""
    return '/api/knowledge/assets/'+attachment_id+'?sig='+asset_signature(settings, attachment_id)

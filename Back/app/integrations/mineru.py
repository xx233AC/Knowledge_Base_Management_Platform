import io
import time
import uuid
import zipfile
from dataclasses import dataclass, field
import httpx
from app.core.errors import BusinessError, require

DEFAULT_BASE_URL = 'https://mineru.net/api/v4'
MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_ZIP_BYTES = 300 * 1024 * 1024
MAX_IMAGES = 300
MAX_IMAGE_BYTES = 150 * 1024 * 1024
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tif', '.tiff')
AUTH_CODES = {'A0202', 'A0211'}


@dataclass
class MinerUResult:
    markdown: str
    images: dict[str, bytes] = field(default_factory=dict)


def _message(body):
    return str(body.get('msg') or body.get('msgCode') or '未知错误')


def _data(response):
    try:
        body = response.json()
    except ValueError as exc:
        raise BusinessError(502, 'MinerU 返回了无法识别的响应') from exc
    if not isinstance(body, dict):
        raise BusinessError(502, 'MinerU 返回了无法识别的响应')
    if body.get('success') is False:
        if str(body.get('msgCode')) in AUTH_CODES:
            raise BusinessError(503, 'MinerU Token 无效或已过期，请更新 API Key')
        raise BusinessError(502, 'MinerU 鉴权失败：'+_message(body))
    code = body.get('code')
    if code not in (0, None):
        text = 'MinerU 解析失败：'+_message(body)
        if code == -60018:
            raise BusinessError(429, text+'（今日额度已用完）')
        if code in {-60002, -60003, -60004, -60005, -60006, -60008}:
            raise BusinessError(400, text)
        raise BusinessError(502, text)
    return body.get('data') or {}


class MinerUClient:
    """MinerU v4 batch-upload adapter: create upload URLs, PUT bytes, poll, unzip markdown."""

    def __init__(self, config, client=None):
        self.base_url = (config.get('base_url') or DEFAULT_BASE_URL).rstrip('/')
        self.token = (config.get('api_key') or '').strip()
        self.model_version = config.get('model_version') or 'pipeline'
        self.enable_ocr = bool(config.get('enable_ocr', True))
        self.language = config.get('language') or 'ch'
        self.poll_seconds = max(0.05, float(config.get('poll_seconds') or 5))
        self.timeout_seconds = max(1.0, float(config.get('timeout_seconds') or 900))
        self.client = client

    def headers(self):
        return {'Authorization': 'Bearer '+self.token, 'Accept': 'application/json'}

    def extract(self, name, data):
        require(bool(self.token), 'MinerU 未配置 API Key，请在系统配置或 .env 中填写', 503)
        require(0 < len(data) <= MAX_FILE_BYTES, 'PDF 超过 MinerU 的 200 MB 单文件限制', 400)
        deadline = time.monotonic()+self.timeout_seconds
        owned = self.client is None
        client = self.client or httpx.Client(timeout=httpx.Timeout(120, connect=10), follow_redirects=True)
        try:
            batch_id, url = self._create_batch(client, name)
            response = client.put(url, content=data)
            require(response.status_code < 400, 'MinerU 文件上传失败（HTTP '+str(response.status_code)+'）', 502)
            result = self._poll(client, batch_id, name, deadline)
            return self._collect(client, result['full_zip_url'])
        finally:
            if owned:
                client.close()

    def _create_batch(self, client, name):
        body = {'files': [{'name': name, 'data_id': uuid.uuid4().hex}],
                'model_version': self.model_version, 'language': self.language,
                'is_ocr': self.enable_ocr, 'enable_formula': True, 'enable_table': True}
        response = client.post(self.base_url+'/file-urls/batch', json=body,
                               headers={**self.headers(), 'Content-Type': 'application/json'})
        data = _data(response)
        urls = data.get('file_urls') or []
        require(bool(data.get('batch_id')) and bool(urls), 'MinerU 未返回上传地址', 502)
        return data['batch_id'], urls[0]

    def _poll(self, client, batch_id, name, deadline):
        url = self.base_url+'/extract-results/batch/'+batch_id
        while True:
            data = _data(client.get(url, headers=self.headers()))
            results = data.get('extract_result') or []
            item = next((r for r in results if r.get('file_name') == name), results[0] if results else None)
            if item:
                state = item.get('state')
                if state == 'done':
                    require(bool(item.get('full_zip_url')), 'MinerU 未返回解析结果地址', 502)
                    return item
                if state == 'failed':
                    raise BusinessError(502, 'MinerU 解析失败：'+str(item.get('err_msg') or '未提供原因'))
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise BusinessError(504, 'MinerU 解析超时，请稍后重试或减少页数')
            time.sleep(min(self.poll_seconds, remaining))

    def _collect(self, client, zip_url):
        response = client.get(zip_url)
        require(response.status_code < 400, 'MinerU 结果下载失败（HTTP '+str(response.status_code)+'）', 502)
        try:
            archive = zipfile.ZipFile(io.BytesIO(response.content))
        except zipfile.BadZipFile as exc:
            raise BusinessError(502, 'MinerU 返回的压缩包无法读取') from exc
        infos = archive.infolist()
        require(len(infos) <= 20000 and sum(i.file_size for i in infos) <= MAX_ZIP_BYTES,
                'MinerU 返回内容超过安全限制', 502)
        marks = [i for i in infos if not i.is_dir() and i.filename.lower().endswith('.md')]
        require(bool(marks), 'MinerU 未返回 Markdown 正文', 502)
        marks.sort(key=lambda i: (0 if i.filename.rsplit('/', 1)[-1].lower() == 'full.md' else 1, len(i.filename)))
        mark = marks[0]
        base = mark.filename.rsplit('/', 1)[0]+'/' if '/' in mark.filename else ''
        images = {}
        for info in infos:
            lower = info.filename.lower()
            if info.is_dir() or not lower.endswith(IMAGE_SUFFIXES):
                continue
            rel = info.filename[len(base):] if base and info.filename.startswith(base) else info.filename
            images[rel] = archive.read(info)
        require(len(images) <= MAX_IMAGES, 'MinerU 返回图片数量超过限制', 502)
        require(sum(len(v) for v in images.values()) <= MAX_IMAGE_BYTES, 'MinerU 返回图片体积超过限制', 502)
        return MinerUResult(archive.read(mark).decode('utf-8', 'replace'), images)

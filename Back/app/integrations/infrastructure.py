from dataclasses import dataclass
from functools import cached_property
import io
import json
from threading import Lock
from pathlib import Path
from app.core.errors import BusinessError, require


class ObjectStorage:
    def __init__(self, settings):
        self.settings = settings

    @cached_property
    def client(self):
        from minio import Minio
        s = self.settings
        require(s.minio_access_key.get_secret_value() and s.minio_secret_key.get_secret_value(),
                '尚未配置 MinIO 凭据', 503)
        return Minio(s.minio_endpoint, access_key=s.minio_access_key.get_secret_value(),
                     secret_key=s.minio_secret_key.get_secret_value(), secure=s.minio_secure)

    def ready(self):
        return self.client.bucket_exists(self.settings.minio_bucket)

    def ensure(self):
        if not self.ready():
            self.client.make_bucket(self.settings.minio_bucket)

    def put(self, key, data, content_type):
        # Explicit init-infrastructure creates the bucket; a typo must not silently create one per request.
        self.client.put_object(self.settings.minio_bucket, key, io.BytesIO(data), len(data),
                               content_type=content_type)

    def get(self, key):
        response = self.client.get_object(self.settings.minio_bucket, key)
        try:
            data = response.read(self.settings.upload_max_bytes + 1)
            require(len(data) <= self.settings.upload_max_bytes, '原始文件超过解析大小限制', 413)
            return data
        finally:
            response.close()
            response.release_conn()

    def stream(self, key):
        response = self.client.get_object(self.settings.minio_bucket, key)
        try:
            yield from response.stream(64 * 1024)
        finally:
            response.close()
            response.release_conn()


class Cache:
    def __init__(self, settings):
        import redis
        self.client = redis.Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True,
                                           socket_connect_timeout=3, socket_timeout=3)

    def ready(self):
        return self.client.ping()

    def get(self, key):
        try:
            value = self.client.get('kb:'+key)
            return json.loads(value) if value else None
        except Exception:
            return None  # Cache is an accelerator; PostgreSQL and ACL remain authoritative.

    def set(self, key, value, ttl=3600):
        try:
            self.client.setex('kb:'+key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception:
            return False
        return True

    def delete(self, key):
        try:
            self.client.delete('kb:'+key)
        except Exception:
            return False
        return True

    def rate_limit(self, key, limit=10, seconds=60):
        script = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n"
        try:
            return int(self.client.eval(script, 1, 'kb:rate:'+key, seconds)) <= limit
        except Exception as exc:
            raise BusinessError(503, '登录限流服务不可用，请检查 Redis 连接') from exc

    def touch_worker(self, ttl=30):
        try:
            self.client.setex('kb:worker:alive', ttl, '1')
            return True
        except Exception:
            return False

    def worker_alive(self):
        """True/False when Redis answers, None when the answer cannot be verified."""
        try:
            return bool(self.client.exists('kb:worker:alive'))
        except Exception:
            return None


def resolve_model_path(path):
    root = Path(path)
    if (root / 'config.json').is_file():
        return root
    master = root / 'snapshots' / 'master'
    if (master / 'config.json').is_file():
        return master
    snapshots = sorted((root / 'snapshots').glob('*/config.json'))
    require(len(snapshots) == 1, '无法确定本地 bge-m3 快照目录，请配置 EMBEDDING_MODEL_PATH', 503)
    return snapshots[0].parent


class LocalEmbedder:
    def __init__(self, settings):
        self.settings, self.lock = settings, Lock()
        self._model = self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise BusinessError(503, '缺少本地向量模型依赖，请安装 embedding 可选依赖') from exc
        path = resolve_model_path(self.settings.embedding_model_path)
        self._tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
        self._model = AutoModel.from_pretrained(str(path), local_files_only=True, use_safetensors=False)
        device = self.settings.embedding_device
        self._model.to(device)
        if self.settings.embedding_dtype == 'float16':
            require(device.startswith('cuda') or device == 'mps', 'float16 仅支持 CUDA 或 MPS 设备', 503)
            self._model.half()
        self._model.eval()
        require(self._model.config.hidden_size == 1024, '向量模型维度与 Milvus 集合不一致', 503)

    def encode(self, texts):
        if not texts:
            return []
        with self.lock:
            self._load()
            import torch
            vectors = []
            for i in range(0, len(texts), self.settings.embedding_batch_size):
                encoded = self._tokenizer(texts[i:i+self.settings.embedding_batch_size], padding=True,
                    truncation=True, max_length=self.settings.embedding_max_tokens, return_tensors='pt')
                encoded = {k: v.to(self.settings.embedding_device) for k, v in encoded.items()}
                with torch.inference_mode():
                    dense = self._model(**encoded).last_hidden_state[:, 0]
                    dense = torch.nn.functional.normalize(dense.float(), p=2, dim=1)
                vectors.extend(dense.cpu().tolist())
            return vectors


class VectorStore:
    def __init__(self, settings):
        self.settings = settings

    @cached_property
    def client(self):
        from pymilvus import MilvusClient
        return MilvusClient(uri=self.settings.milvus_uri,
                            token=self.settings.milvus_token.get_secret_value(), timeout=10)

    def ready(self):
        return self.client.has_collection(self.settings.milvus_collection)

    def ensure(self):
        from pymilvus import DataType, MilvusClient
        name = self.settings.milvus_collection
        if self.client.has_collection(name):
            info = self.client.describe_collection(name)
            fields = {x['name']: x for x in info['fields']}
            require('dense_vector' in fields and int(fields['dense_vector']['params']['dim']) == 1024,
                    '已有 Milvus 集合结构不兼容，禁止自动删除；请使用新集合名', 409)
            require({'chunk_id', 'unit_id', 'version', 'content_hash', 'model_id'} <= set(fields),
                    'Milvus 集合缺少业务关联字段，禁止直接复用', 409)
            return
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field('chunk_id', DataType.VARCHAR, is_primary=True, max_length=36)
        schema.add_field('unit_id', DataType.VARCHAR, max_length=36)
        schema.add_field('version', DataType.INT64)
        schema.add_field('content_hash', DataType.VARCHAR, max_length=64)
        schema.add_field('model_id', DataType.VARCHAR, max_length=100)
        schema.add_field('dense_vector', DataType.FLOAT_VECTOR, dim=1024)
        indexes = self.client.prepare_index_params()
        indexes.add_index(field_name='dense_vector', index_type='HNSW', metric_type='COSINE',
                          params={'M': 16, 'efConstruction': 200})
        indexes.add_index(field_name='unit_id', index_type='INVERTED')
        self.client.create_collection(name, schema=schema, index_params=indexes, consistency_level='Strong')

    def upsert(self, rows):
        for start in range(0, len(rows), 128):
            self.client.upsert(self.settings.milvus_collection, rows[start:start+128])

    def delete_unit(self, unit_id, before_version=None):
        from uuid import UUID
        unit_id = str(UUID(unit_id))
        expression = 'unit_id == '+json.dumps(unit_id)
        if before_version is not None:
            expression += ' and version < '+str(int(before_version))
        self.client.delete(self.settings.milvus_collection, filter=expression)

    def search(self, vector, limit):
        results = self.client.search(self.settings.milvus_collection, data=[vector], limit=limit,
             search_params={'metric_type': 'COSINE', 'params': {'ef': max(64, limit)}},
             output_fields=['unit_id', 'version', 'content_hash', 'model_id'], consistency_level='Strong')
        return [dict(chunk_id=h.get('chunk_id') or h.get('id'), unit_id=h['entity']['unit_id'],
                     version=h['entity']['version'], score=h['distance']) for h in results[0]]


@dataclass
class Infrastructure:
    storage: ObjectStorage
    cache: Cache
    vectors: VectorStore
    embedder: LocalEmbedder

    @classmethod
    def from_settings(cls, settings):
        return cls(ObjectStorage(settings), Cache(settings), VectorStore(settings), LocalEmbedder(settings))

"""Enrich parsed document figures before chunking; original figures remain in MinIO."""
import io
import re
import warnings
from PIL import Image, UnidentifiedImageError
from app.core.errors import BusinessError, require
from app.integrations.llm import LLMGateway
from app.integrations.parser import ParsedDocument


def prepare_image(data):
    require(0 < len(data) <= 32*1024*1024, '文档插图为空或超过 32 MiB 限制')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                require(image.width*image.height <= 40_000_000, '文档插图像素过大')
                image_format = image.format
                width, height = image.size
                image.verify()
            mime = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif', 'WEBP': 'image/webp'}
            if image_format in mime and max(width, height) <= 8192:
                return data, mime[image_format]
            with Image.open(io.BytesIO(data)) as image:
                image.thumbnail((8192, 8192))
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
                output = io.BytesIO()
                image.save(output, format='PNG')
                converted = output.getvalue()
                require(len(converted) <= 32*1024*1024, '转换后的插图超过 32 MiB 限制')
                return converted, 'image/png'
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise BusinessError(400, '文档插图损坏或无法安全读取，请检查原文件') from None


class DocumentImageAnalyzer:
    def __init__(self, config):
        self.config = config

    def enrich(self, parsed, active):
        require(len(parsed.images) <= self.config.get('vision_max_images', 100),
                '文档插图数量超过图片分析上限，请拆分文档或调整 LLM_VISION_MAX_IMAGES')
        body = parsed.body
        gateway = LLMGateway(self.config)
        for path, original in parsed.images.items():
            if not active():
                return None
            data, mime = prepare_image(original)
            offset = body.find(path)
            context = body[max(0, offset-700):offset+700] if offset >= 0 else body[:1400]
            description = gateway.analyze_image(data, mime, context)
            if not active():
                return None
            annotation = '\n\n**图片内容分析（AI 生成，需核对原图）**\n\n'+description+'\n\n'
            pattern = re.compile(r'!\[[^\]]*\]\((?:\./)?'+re.escape(path)+r'\)')
            if pattern.search(body):
                body = pattern.sub(lambda match: match.group(0)+annotation, body)
            else:
                body += '\n\n![文档插图]('+path+')'+annotation
            require(len(body) <= 2_000_000, '图片分析后的文档超过 200 万字符限制')
        return ParsedDocument(body, parsed.images)

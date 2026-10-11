"""剩余公开 API 适配；Python 3.9，SDK 仅在对应厂商被调用时导入。"""
import base64
import hashlib
import hmac
import io
import json
import os
import time
import urllib.parse
import wave
from email.utils import formatdate

PROVIDERS = ('openai', 'fish', 'xfyun', 'google', 'polly', 'baidu', 'cartesia')
SOURCES = {
    'openai': 'https://developers.openai.com/api/docs/guides/text-to-speech',
    'fish': 'https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech',
    'xfyun': 'https://www.xfyun.cn/doc/tts/online_tts/API.html',
    'google': 'https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize',
    'polly': 'https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html',
    'baidu': 'https://bce.bdstatic.com/p3m/pdf/ai-cloud-share/online/SPEECH/SPEECH.pdf',
    'cartesia': 'https://docs.cartesia.ai/api-reference/tts/bytes',
}
OPENAI_VOICES = ('alloy', 'ash', 'ballad', 'coral', 'echo', 'fable', 'nova', 'onyx', 'sage', 'shimmer', 'verse', 'marin', 'cedar')
CARTESIA_VERSION = '2026-08-14'


def google_headers(c):
    headers = {'Authorization': 'Bearer ' + c.key('GOOGLE_ACCESS_TOKEN')}
    if os.environ.get('GOOGLE_QUOTA_PROJECT'):
        headers['x-goog-user-project'] = os.environ['GOOGLE_QUOTA_PROJECT']
    return headers


def cartesia_headers(c):
    return {'Authorization': 'Bearer ' + c.key('CARTESIA_API_KEY'), 'Cartesia-Version': CARTESIA_VERSION}


def polly_client(c):
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise c.TTSError('Polly 需要项目虚拟环境中的 boto3；见 usage.md 安装说明。') from None
    # 显式凭据，避免读取其他项目/共享账号文件或实例元数据。
    return boto3.client('polly', region_name=c.key('AWS_REGION'),
                        aws_access_key_id=c.key('AWS_ACCESS_KEY_ID'),
                        aws_secret_access_key=c.key('AWS_SECRET_ACCESS_KEY'),
                        aws_session_token=os.environ.get('AWS_SESSION_TOKEN') or None,
                        config=Config(connect_timeout=30, read_timeout=120, ignore_configured_endpoint_urls=True,
                                      retries={'total_max_attempts': 1}, signature_version='v4'))


def polly_call(c, api, method, **kwargs):
    try:
        return getattr(api, method)(**kwargs)
    except Exception:
        # SDK 错误可含用户文本/签名URL；只输出固定说明，不自动重试。
        raise c.TTSError('Polly 请求失败：检查凭据、区域、音色/engine 和额度；未自动重试。') from None


def live_voices(c, provider):
    if provider == 'openai':
        return {'scope': '官方预置目录；不包含账号自定义声音', 'voices': c.catalog('openai')}
    if provider in ('xfyun', 'baidu'):
        raise c.TTSError('该产品没有已核实的通用账号音色列表 API；使用公开目录候选并在控制台确认权限。')
    if provider == 'google':
        data = c.load_json('https://texttospeech.googleapis.com/v1/voices', google_headers(c))
        if 'error' in data or not isinstance(data.get('voices'), list):
            raise c.TTSError('Google Cloud 未返回完整音色目录。')
        return {'scope': 'Cloud TTS 官方目录；保留 languageCodes/ssmlGender/naturalSampleRateHertz', 'voices': data['voices']}
    if provider == 'polly':
        api = polly_client(c)
        try:
            rows, token, seen = [], None, set()
            while True:
                data = polly_call(c, api, 'describe_voices', **({'NextToken': token} if token else {}))
                rows.extend(data['Voices'])
                token = data.get('NextToken')
                if not token:
                    return {'scope': '当前 AWS 区域目录；完整分页，保留 SupportedEngines', 'voices': rows}
                if token in seen:
                    raise c.TTSError('Polly 重复分页令牌，停止查询。')
                seen.add(token)
        finally:
            api.close()
    if provider == 'fish':
        rows, page, seen = [], 1, set()
        while True:
            data = c.load_json('https://api.fish.audio/model?' + urllib.parse.urlencode({'page_size': 100, 'page_number': page, 'self': 'true'}), {'Authorization': 'Bearer ' + c.key('FISH_API_KEY')})
            batch = data.get('items')
            if not isinstance(batch, list):
                raise c.TTSError('Fish 未返回模型目录。')
            ids = tuple(v['_id'] for v in batch)
            if batch and ids in seen:
                raise c.TTSError('Fish 重复目录分页，停止查询。')
            seen.add(ids)
            rows.extend(batch)
            if data.get('window_limited'):
                raise c.TTSError('Fish 目录超过可查询窗口；未返回不完整目录。')
            more = data.get('has_more')
            if more is False or (more is None and len(rows) >= data.get('total', float('inf'))):
                return {'scope': '当前工作空间自有音色模型，完整分页；不代表全部社区库', 'voices': rows}
            if not batch or (more is None and 'total' not in data):
                raise c.TTSError('Fish 分页状态缺失；未返回不完整目录。')
            page += 1
    if provider == 'cartesia':
        rows, token, seen = [], None, set()
        while True:
            query = {'limit': 100, 'expand[]': 'preview_file_url'}
            if token:
                query['starting_after'] = token
            data = c.load_json('https://api.cartesia.ai/voices?' + urllib.parse.urlencode(query), cartesia_headers(c))
            batch = data.get('data')
            if not isinstance(batch, list):
                raise c.TTSError('Cartesia 未返回音色数组。')
            rows.extend(batch)
            if data.get('has_more') is False:
                return {'scope': '当前账号可见音色，完整分页；保留描述、语言和试听地址', 'voices': rows}
            token = data.get('next_page')
            if data.get('has_more') is not True or not batch or not token or token in seen:
                raise c.TTSError('Cartesia 分页状态缺失或令牌重复。')
            seen.add(token)
    raise c.TTSError('未支持的厂商。')


def pcm_wav(c, data, sample_rate=16000):
    if not data or len(data) % 2:
        raise c.TTSError('PCM 音频为空或不是完整的16位采样。')
    out = io.BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(data)
    return out.getvalue()


def xfyun_url(api_key, secret, timestamp=None):
    host = 'tts-api.xfyun.cn'
    date = formatdate(time.time() if timestamp is None else timestamp, usegmt=True)
    canonical = 'host: %s\ndate: %s\nGET /v2/tts HTTP/1.1' % (host, date)
    signature = base64.b64encode(hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).digest()).decode()
    origin = 'api_key="%s", algorithm="hmac-sha256", headers="host date request-line", signature="%s"' % (api_key, signature)
    return 'wss://' + host + '/v2/tts?' + urllib.parse.urlencode({'authorization': base64.b64encode(origin.encode()).decode(), 'date': date, 'host': host})


def synth_xfyun(c, args, text):
    if len(text.encode('utf-8')) >= 8000:
        raise c.TTSError('讯飞文稿必须少于8000 UTF-8字节，请先分段。')
    if args.model or args.style or args.speed != 1:
        raise c.TTSError('讯飞不映射 --model/--style/--speed；原生语速用 --xfyun-speed（0–100）。')
    known = [v for v in c.catalog('xfyun') if v['id'] == args.voice]
    if known and not any(v.get('runnable', False) and 'xfyun.online.v2' in v.get('api_profiles', []) for v in known):
        raise c.TTSError('该讯飞音色属于超拟人或长文本产品；当前生成器仅接入在线 /v2/tts，请按目录选择对应接口。')
    speed = getattr(args, 'xfyun_speed', 50)
    if not 0 <= speed <= 100:
        raise c.TTSError('讯飞 --xfyun-speed 必须在0–100。')
    try:
        import websocket
    except ImportError:
        raise c.TTSError('讯飞需要项目虚拟环境中的 websocket-client；见 usage.md。') from None
    url = xfyun_url(c.key('XFYUN_API_KEY'), c.key('XFYUN_API_SECRET'))
    body = {'common': {'app_id': c.key('XFYUN_APP_ID')},
            'business': {'aue': 'lame' if args.format == 'mp3' else 'raw', 'auf': 'audio/L16;rate=16000',
                         'vcn': args.voice, 'tte': 'UTF8', 'speed': speed},
            'data': {'status': 2, 'text': base64.b64encode(text.encode('utf-8')).decode()}}
    ws = None
    try:
        ws = websocket.create_connection(url, timeout=30, redirect_limit=0)
        handshake = getattr(ws, 'handshake_response', None)
        if handshake is not None and handshake.status != 101:
            raise c.TTSError('讯飞握手失败或发生重定向；未发送文稿。')
        ws.send(json.dumps(body, ensure_ascii=False))
        chunks, deadline = [], time.monotonic() + 120
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise c.TTSError('讯飞会话超时；未发布部分音频，未自动重试。')
            ws.settimeout(remaining)
            frame = ws.recv()
            if not frame:
                raise c.TTSError('讯飞会话提前关闭；未发布部分音频。')
            data = json.loads(frame)
            if data.get('code') != 0:
                raise c.TTSError('讯飞业务错误；检查音色权限、鉴权和额度。')
            block = data.get('data')
            if block is None:
                continue
            if block.get('audio'):
                chunks.append(base64.b64decode(block['audio'], validate=True))
            if block.get('status') == 2:
                audio = b''.join(chunks)
                return (pcm_wav(c, audio) if args.format == 'wav' else audio), 'online-tts/v2'
    except c.TTSError:
        raise
    except Exception:
        raise c.TTSError('讯飞连接或响应失败；未发布部分音频，未自动重试。') from None
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


def synth(c, args, text):
    language = getattr(args, 'language', None)
    if args.provider == 'openai':
        model = args.model or 'gpt-4o-mini-tts'
        if model not in ('gpt-4o-mini-tts', 'gpt-4o-mini-tts-2025-12-15', 'tts-1', 'tts-1-hd'):
            raise c.TTSError('OpenAI 当前只支持官方已核查的 Speech 模型。')
        voices = OPENAI_VOICES if model.startswith('gpt-4o-mini-tts') else ('alloy', 'ash', 'coral', 'echo', 'fable', 'onyx', 'nova', 'sage', 'shimmer')
        if args.voice not in voices or len(text) > 4096 or not 0.25 <= args.speed <= 4:
            raise c.TTSError('OpenAI 音色/模型不匹配、文稿超过4096字符或语速不在0.25–4。')
        if args.style and model in ('tts-1', 'tts-1-hd'):
            raise c.TTSError('tts-1/tts-1-hd 不支持风格 instructions。')
        if args.style and len(args.style) > 4096:
            raise c.TTSError('OpenAI instructions 最多4096字符。')
        body = {'model': model, 'input': text, 'voice': args.voice, 'response_format': args.format, 'speed': args.speed}
        if args.style:
            body['instructions'] = args.style
        with c.request('https://api.openai.com/v1/audio/speech', {'Authorization': 'Bearer ' + c.key('OPENAI_API_KEY')}, body) as r:
            return r.read(), model
    if args.provider == 'fish':
        model = args.model or 's2.1-pro'
        if model not in ('s1', 's2-pro', 's2.1-pro', 's2.1-pro-free', 'drama-3-preview'):
            raise c.TTSError('Fish 模型不在已核查目录中。')
        if args.style or args.speed != 1:
            raise c.TTSError('Fish 当前不映射 --style/--speed，避免改变用户文稿。')
        body = {'text': text, 'reference_id': args.voice, 'format': args.format}
        with c.request('https://api.fish.audio/v1/tts', {'Authorization': 'Bearer ' + c.key('FISH_API_KEY'), 'model': model}, body) as r:
            return r.read(), model
    if args.provider == 'xfyun':
        return synth_xfyun(c, args, text)
    if args.provider == 'google':
        if args.model or args.style or not 0.25 <= args.speed <= 2:
            raise c.TTSError('Google Cloud 基础合成不映射 model/style，speed 为0.25–2。')
        if len(text.encode('utf-8')) > 5000:
            raise c.TTSError('Google Cloud 文稿最多5000 UTF-8字节，请先分段。')
        body = {'input': {'text': text}, 'voice': {'name': args.voice, 'languageCode': language or '-'.join(args.voice.split('-')[:2])},
                'audioConfig': {'audioEncoding': 'MP3' if args.format == 'mp3' else 'LINEAR16'}}
        # Chirp HD/3 HD 不支持 speakingRate；默认速度时不发送该参数。
        if args.speed != 1 and 'Chirp' in args.voice:
            raise c.TTSError('Chirp 音色不支持此客户端的 speakingRate，请使用默认 --speed。')
        if args.speed != 1:
            body['audioConfig']['speakingRate'] = args.speed
        data = c.load_json('https://texttospeech.googleapis.com/v1/text:synthesize', google_headers(c), body)
        if 'error' in data or not data.get('audioContent'):
            raise c.TTSError('Google Cloud 业务错误或未返回音频。')
        return base64.b64decode(data['audioContent'], validate=True), 'Cloud-TTS/v1'
    if args.provider == 'polly':
        engine = args.model or 'standard'
        if engine not in ('standard', 'neural', 'long-form', 'generative') or args.style or args.speed != 1:
            raise c.TTSError('Polly --model 为 engine；此客户端不映射 style/speed。')
        known = [v for v in c.catalog('polly') if v['id'] == args.voice and (not language or v['language'] == language)]
        if known and not any(v.get('runnable', False) and engine in v['supported_engines'] for v in known):
            raise c.TTSError('Polly 音色与 engine 不匹配，或精确 API VoiceId 尚未核实；请查询目录并设置 --model。')
        if len(text) > 3000:
            raise c.TTSError('Polly 单次最多3000计费字符，请先分段。')
        body = {'Text': text, 'TextType': 'text', 'VoiceId': args.voice, 'Engine': engine,
                'OutputFormat': 'mp3' if args.format == 'mp3' else 'pcm',
                'SampleRate': '24000' if args.format == 'mp3' else '16000'}
        if language:
            body['LanguageCode'] = language
        api = polly_client(c)
        try:
            response = polly_call(c, api, 'synthesize_speech', **body)
            stream = response.get('AudioStream')
            if stream is None:
                raise c.TTSError('Polly 未返回音频流。')
            try:
                audio = stream.read()
            except Exception:
                raise c.TTSError('Polly 音频流读取失败；未发布部分音频，未自动重试。') from None
            finally:
                stream.close()
            return (pcm_wav(c, audio) if args.format == 'wav' else audio), engine
        finally:
            api.close()
    if args.provider == 'baidu':
        if args.model or args.style or args.speed != 1:
            raise c.TTSError('百度短文本不映射 model/style/speed；语速用 --baidu-speed（0–15）。')
        speed = getattr(args, 'baidu_speed', 5)
        try:
            size = len(text.encode('gbk'))
        except UnicodeEncodeError:
            raise c.TTSError('百度短文本仅处理GBK可表示的中英文文本；请移除不支持的字符。') from None
        if not 0 <= speed <= 15 or not args.voice.isdecimal() or size >= 1024:
            raise c.TTSError('百度 per 必须为整数，文稿须少于1024 GBK字节，baidu-speed 为0–15。')
        form = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': c.key('BAIDU_API_KEY'), 'client_secret': c.key('BAIDU_SECRET_KEY')}).encode()
        data = c.load_json('https://aip.baidubce.com/oauth/2.0/token', {'Content-Type': 'application/x-www-form-urlencoded'}, form)
        token = data.get('access_token')
        if not token or data.get('error'):
            raise c.TTSError('百度令牌获取失败；检查 API Key/Secret Key 和权限。')
        # 百度 tex 要两次 urlencode：先转义文本，再转义整个表单。
        body = urllib.parse.urlencode({'tex': urllib.parse.quote(text, safe=''), 'tok': token, 'cuid': 'alltts-local',
                                      'ctp': 1, 'lan': 'zh', 'per': int(args.voice), 'spd': speed,
                                      'aue': 3 if args.format == 'mp3' else 6}).encode()
        with c.request('https://tsn.baidu.com/text2audio', {'Content-Type': 'application/x-www-form-urlencoded'}, body) as r:
            audio = r.read()
            if not r.headers.get('Content-Type', '').lower().startswith('audio/'):
                raise c.TTSError('百度未返回 audio 内容类型；未发布输出。')
        if audio.lstrip().startswith((b'{', b'[')):
            raise c.TTSError('百度返回业务错误 JSON；检查权限、音库与额度。')
        return audio, 'short-text/text2audio'
    if args.provider == 'cartesia':
        model = args.model or 'sonic-3.6'
        if model not in ('sonic-3.6', 'sonic-3.5', 'sonic-3', 'sonic-latest') or args.style or not 0.6 <= args.speed <= 1.5:
            raise c.TTSError('Cartesia 使用 Sonic 3 系列，speed 为0.6–1.5；自由文本 style 未映射。')
        fmt = {'container': args.format, 'sample_rate': 44100}
        fmt.update({'bit_rate': 128000} if args.format == 'mp3' else {'encoding': 'pcm_s16le'})
        body = {'model_id': model, 'transcript': text, 'voice': args.voice, 'output_format': fmt, 'generation_config': {'speed': args.speed}}
        if language:
            body['language'] = language
        with c.request('https://api.cartesia.ai/tts/bytes', cartesia_headers(c), body) as r:
            return r.read(), model
    raise c.TTSError('未支持的厂商。')

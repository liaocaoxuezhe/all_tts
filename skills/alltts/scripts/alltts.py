#!/usr/bin/env python3
"""Python 3.9+，基础标准库、可选 SDK 的 P0/P1 TTS 客户端。"""
import argparse
import base64
import json
import http.client
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import datetime
import hashlib
import hmac
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# 直接执行及 importlib 加载均能定位相邻模块。
sys.path.insert(0, str(Path(__file__).resolve().parent))
import extra_providers as extra

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ('minimax', 'volcengine', 'gemini', 'system', 'aliyun', 'tencent', 'azure', 'elevenlabs') + extra.PROVIDERS
SOURCES = {
    'minimax': 'https://platform.minimax.cn/docs/api-reference/speech-t2a-http',
    'volcengine': 'https://docs.volcengine.com/docs/DoubaoVoice/unidirectional-streaming-text-to-speech-http?lang=zh',
    'gemini': 'https://ai.google.dev/gemini-api/docs/speech-generation',
    'system': '本机已安装语音引擎',
    'aliyun': 'https://help.aliyun.com/zh/model-studio/qwen-tts-api',
    'tencent': 'https://cloud.tencent.com/document/api/1073/37995',
    'azure': 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech',
    'elevenlabs': 'https://elevenlabs.io/docs/api-reference/text-to-speech/convert',
}

SOURCES.update(extra.SOURCES)

class TTSError(Exception):
    pass

def emit(value):
    print(redact(json.dumps(value, ensure_ascii=False, indent=2)))

def key(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise TTSError('缺少环境变量 ' + name + '；请在本机配置，不要将密钥写进聊天或技能文件。')
    return value

def redact(text):
    for name in ('MINIMAX_API_KEY', 'VOLCENGINE_API_KEY', 'GEMINI_API_KEY',
                 'DASHSCOPE_API_KEY', 'TENCENT_SECRET_ID', 'TENCENT_SECRET_KEY',
                 'TENCENT_TOKEN', 'AZURE_SPEECH_KEY', 'ELEVENLABS_API_KEY',
                 'OPENAI_API_KEY', 'FISH_API_KEY', 'XFYUN_APP_ID', 'XFYUN_API_KEY', 'XFYUN_API_SECRET',
                 'GOOGLE_ACCESS_TOKEN', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN',
                 'BAIDU_API_KEY', 'BAIDU_SECRET_KEY', 'CARTESIA_API_KEY'):
        secret = os.environ.get(name, '').strip()
        if secret:
            for variant in sorted({secret, json.dumps(secret, ensure_ascii=False)[1:-1],
                                   urllib.parse.quote(secret, safe=''),
                                   urllib.parse.quote_plus(secret)}, key=len, reverse=True):
                text = text.replace(variant, '[REDACTED]')
    return text

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TTSError('拒绝 HTTP 重定向，避免凭据传到其他地址；未自动重试。')

# 每个请求均使用此 opener，不修改宿主应用的全局 opener。
HTTP = urllib.request.build_opener(NoRedirect())

def _plain_code(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 0 <= value <= 10 ** 12:
        return value
    if isinstance(value, str) and re.fullmatch(r'[0-9]{1,12}', value):
        return int(value)
    return None

def _submitted_transcript(body):
    if isinstance(body, bytes):
        try:
            body = json.loads(body.decode('utf-8'))
        except (UnicodeError, json.JSONDecodeError):
            return ''
    if not isinstance(body, dict):
        return ''
    params = body.get('req_params')
    if isinstance(params, dict) and isinstance(params.get('text'), str):
        return params['text']
    text = body.get('text')
    return text if isinstance(text, str) else ''

def _safe_provider_message(message, transcript):
    # 只保留短诊断句。密钥、用户文稿、以及引号/换行等可能夹带原文的内容一律不回显。
    if not isinstance(message, str):
        return ''
    collapsed = ' '.join(message.split())
    if not re.fullmatch(r'[\w .,:;_=\-\[\]()]{1,200}', collapsed):
        return ''
    folded = ' '.join(transcript.split()) if isinstance(transcript, str) else ''
    if folded and (collapsed == folded or (len(folded) >= 4 and folded in collapsed)):
        return ''
    cleaned = redact(collapsed)
    if not re.fullmatch(r'[\w .,:;_=\-\[\]()]{1,200}', cleaned):
        return ''
    return cleaned

def _volcengine_http_detail(hostname, error, body):
    # 新版控制台 403 常见为 {"code":45000030,"message":"requested resource not granted"}。
    if (hostname or '').lower() != 'openspeech.bytedance.com':
        return ''
    try:
        data = json.loads(error.read(8192).decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError, OSError, AttributeError, ValueError):
        return ''
    if not isinstance(data, dict):
        return ''
    header = data.get('header') if isinstance(data.get('header'), dict) else {}
    code = _plain_code(data.get('code'))
    if code is None:
        code = _plain_code(header.get('code'))
    message = data.get('message') if isinstance(data.get('message'), str) else header.get('message')
    safe = _safe_provider_message(message, _submitted_transcript(body))
    if safe and code is not None:
        return '%s（code %s）' % (safe, code)
    if safe:
        return safe
    if code is not None:
        return 'code %s' % code
    return ''

def request(url, headers, body=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise TTSError('请求只允许不含用户凭据的 HTTPS 地址。')
    payload = body if isinstance(body, bytes) else (None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8'))
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json', **headers})
    try:
        return HTTP.open(req, timeout=120)
    except urllib.error.HTTPError as e:
        # 不回显服务商原文，避免带出密钥或用户文稿。火山 HTTP 403 只附加白名单内的 code 与 message。
        detail = _volcengine_http_detail(parsed.hostname, e, body) if e.code == 403 else ''
        try:
            e.close()
        except OSError:
            pass
        hint = '检查密钥、账号区域、权限、模型和额度；未自动重试。'
        if detail:
            raise TTSError('HTTP %s：%s；%s' % (e.code, detail, hint)) from None
        raise TTSError('HTTP %s：%s' % (e.code, hint)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise TTSError('网络连接失败或超时；生成请求可能已计费，未自动重试。') from None

def load_json(url, headers, body=None):
    with request(url, headers, body) as response:
        return json.load(response)

def check_minimax(data):
    code = data.get('base_resp', {}).get('status_code')
    if code != 0:
        raise TTSError('MiniMax 业务错误：%s；检查官方错误码。' % code)

def catalog(provider=None):
    all_rows = []
    if provider in ('elevenlabs', 'fish', 'cartesia'):
        raise TTSError('该厂商使用账号/区域目录，请运行 voices --provider ' + provider + ' --live。')
    for p in ('minimax', 'volcengine', 'gemini', 'aliyun', 'tencent', 'openai', 'xfyun', 'baidu', 'azure', 'google', 'polly'):
        if provider and p != provider:
            continue
        all_rows.extend(json.loads((ROOT / 'references' / (p + '-voices.json')).read_text(encoding='utf-8'))['voices'])
    return all_rows

def run_local(args, **kwargs):
    try:
        return subprocess.run(args, check=True, capture_output=True, encoding='utf-8', timeout=120, **kwargs).stdout
    except (subprocess.SubprocessError, OSError):
        raise TTSError('本地语音命令失败；检查已安装音色、引擎和输出权限。') from None

def powershell(script, env=None):
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    return run_local(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], env=env)

def system_voices():
    system = platform.system()
    if system == 'Darwin':
        result = []
        for line in run_local(['say', '-v', '?']).splitlines():
            m = re.match(r'(.+?)\s+([a-z]{2,3}_[A-Z]{2})\s+#\s*(.*)', line)
            if m:
                result.append({'provider': 'system', 'os': 'macOS', 'id': m[1].strip(), 'name': m[1].strip(), 'language': m[2], 'sample_text': m[3]})
        return result
    if system == 'Windows':
        script = """[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $v=@($s.GetInstalledVoices() | ForEach-Object { @{provider='system';os='Windows';id=$_.VoiceInfo.Name;name=$_.VoiceInfo.Name;language=$_.VoiceInfo.Culture.Name;enabled=$_.Enabled} }); ConvertTo-Json -InputObject $v -Depth 4 -Compress"""
        return json.loads(powershell(script).lstrip('\ufeff'))
    if system == 'Linux':
        if not shutil.which('espeak-ng'):
            raise TTSError('Linux 没有统一自带 TTS；当前未安装 espeak-ng。请自行选择安装引擎。')
        result = []
        for line in run_local(['espeak-ng', '--voices']).splitlines()[1:]:
            c = line.split()
            if len(c) >= 5:
                result.append({'provider': 'system', 'os': 'Linux/espeak-ng', 'id': c[4], 'name': c[3], 'language': c[1]})
        return result
    raise TTSError('不支持的系统：' + system)

def _client_context():
    from types import SimpleNamespace
    return SimpleNamespace(**globals())

def live_voices(provider):
    if provider in extra.PROVIDERS:
        return extra.live_voices(_client_context(), provider)
    if provider == 'azure':
        rows = load_json(azure_base() + '/cognitiveservices/voices/list', {'Ocp-Apim-Subscription-Key': key('AZURE_SPEECH_KEY')})
        if not isinstance(rows, list):
            raise TTSError('Azure 未返回音色数组。')
        return {'scope': '当前资源区域可见音色，包含 Locale/StyleList/RolePlayList 等官方字段', 'voices': rows}
    if provider == 'elevenlabs':
        rows, token, seen = [], '', set()
        while True:
            query = {'page_size': 100}
            if token:
                query['next_page_token'] = token
            data = load_json('https://api.elevenlabs.io/v2/voices?' + urllib.parse.urlencode(query), {'xi-api-key': key('ELEVENLABS_API_KEY')})
            rows.extend(data['voices'])
            if data.get('has_more') is False:
                return {'scope': '当前账号可见音色，已遍历分页；保留 description/labels/preview_url', 'voices': rows}
            token = data.get('next_page_token')
            if not data.get('has_more') or not token or token in seen:
                raise TTSError('ElevenLabs 分页状态缺失或令牌重复，未返回不完整目录。')
            seen.add(token)
    if provider in ('aliyun', 'tencent'):
        raise TTSError('该厂商当前使用官方公开音色快照；未实现账号/克隆音色实时列表。请去掉 --live。')
    if provider == 'system':
        return {'scope': '当前系统实际可用音色', 'voices': system_voices()}
    if provider == 'minimax':
        base = os.environ.get('MINIMAX_REGION', 'cn')
        if base not in ('cn', 'global'):
            raise TTSError('MINIMAX_REGION 必须是 cn 或 global')
        host = 'https://api.minimax.cn' if base == 'cn' else 'https://api.minimax.io'
        data = load_json(host + '/v1/get_voice', {'Authorization': 'Bearer ' + key('MINIMAX_API_KEY')}, {'voice_type': 'all'})
        check_minimax(data)
        return {'scope': '当前账号音色，包含官方 description；尚未激活的克隆音色可能不可见', 'data': data}
    if provider == 'gemini':
        rows, token, seen = [], '', set()
        while True:
            query = urllib.parse.urlencode({'page_token': token}) if token else ''
            data = load_json('https://generativelanguage.googleapis.com/v1beta/voices' + ('?' + query if query else ''), {'x-goog-api-key': key('GEMINI_API_KEY')})
            rows.extend(data.get('voices', []))
            token = data.get('next_page_token') or data.get('nextPageToken')
            if not token:
                return {'scope': '当前项目扩展/自定义目录，已遍历分页', 'voices': rows}
            if token in seen:
                raise TTSError('音色列表重复分页令牌，停止以避免死循环。')
            seen.add(token)
    raise TTSError('火山当前使用公开文档全表；账号授权音色请在控制台音色库确认。未编造列表 API。')

# 单向流式 HTTP/SSE 的合成结束成功码。见火山引擎文档「音频合成结束的成功状态码」。
VOLC_STREAM_DONE = 20000000

def decode_volc(response):
    # HTTP chunked 不等于 SSE；接受逐行 JSON，也接受 data: 包装。
    # code 0 是音频块；20000000 表示合成正常结束，不能当成业务错误丢掉已收到的音频。
    chunks = []
    for raw in response:
        line = raw.decode('utf-8').strip()
        if not line or line.startswith(':') or line.startswith('event:'):
            continue
        if line.startswith('data:'):
            line = line[5:].strip()
        if line == '[DONE]':
            continue
        data = json.loads(line)
        code = data.get('code')
        if code == VOLC_STREAM_DONE:
            if data.get('data'):
                chunks.append(base64.b64decode(data['data'], validate=True))
            break
        if code != 0:
            raise TTSError('火山业务错误：%s；未保存不完整音频。' % code)
        if data.get('data'):
            chunks.append(base64.b64decode(data['data'], validate=True))
    return b''.join(chunks)

def azure_base():
    region = key('AZURE_SPEECH_REGION')
    if not re.fullmatch(r'[a-z0-9-]+', region):
        raise TTSError('AZURE_SPEECH_REGION 应填写资源区域，例如 eastasia。')
    return 'https://' + region + '.tts.speech.microsoft.com'

def tc3_authorization(payload, secret_id, secret_key, timestamp, host='tts.tencentcloudapi.com', service='tts', action='TextToVoice'):
    # 与发送的 UTF-8 字节完全相同；UTC 日期，不能使用本机时区。
    date = datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')
    signed = 'content-type;host;x-tc-action'
    headers = 'content-type:application/json; charset=utf-8\nhost:%s\nx-tc-action:%s\n' % (host, action.lower())
    canonical = 'POST\n/\n\n' + headers + '\n' + signed + '\n' + hashlib.sha256(payload).hexdigest()
    scope = date + '/' + service + '/tc3_request'
    message = 'TC3-HMAC-SHA256\n%s\n%s\n%s' % (timestamp, scope, hashlib.sha256(canonical.encode('utf-8')).hexdigest())
    signing = ('TC3' + secret_key).encode('utf-8')
    for part in (date, service, 'tc3_request'):
        signing = hmac.new(signing, part.encode('utf-8'), hashlib.sha256).digest()
    signature = hmac.new(signing, message.encode('utf-8'), hashlib.sha256).hexdigest()
    return 'TC3-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s' % (secret_id, scope, signed, signature)

def synth_p1(args, text):
    if args.provider == 'aliyun':
        model = args.model or 'qwen3-tts-flash'
        if model != 'qwen3-tts-flash':
            raise TTSError('百炼当前仅实现 qwen3-tts-flash；其他系列协议与音色需单独接入。')
        if args.style or args.speed != 1:
            raise TTSError('当前百炼 Qwen-TTS 不映射 --style/--speed。')
        if len(text) > 600:
            raise TTSError('Qwen-TTS 文稿最多 600 字符，请先分段。')
        if args.voice not in [v['id'] for v in catalog('aliyun') if v['runnable']]:
            raise TTSError('该音色不在 qwen3-tts-flash 官方目录中。')
        region = os.environ.get('DASHSCOPE_REGION', 'cn')
        hosts = {'cn': 'dashscope.aliyuncs.com', 'intl': 'dashscope-intl.aliyuncs.com'}
        if region not in hosts:
            raise TTSError('DASHSCOPE_REGION 必须是 cn（北京）或 intl（新加坡）。')
        language = getattr(args, 'language', None) or 'Auto'
        if language not in ('Auto', 'Chinese', 'English', 'German', 'Italian', 'Portuguese', 'Spanish', 'Japanese', 'Korean', 'French', 'Russian'):
            raise TTSError('百炼 --language 应为官方 language_type，例如 Auto/Chinese/English。')
        body = {'model': model, 'input': {'text': text, 'voice': args.voice, 'language_type': language}}
        data = load_json('https://' + hosts[region] + '/api/v1/services/aigc/multimodal-generation/generation', {'Authorization': 'Bearer ' + key('DASHSCOPE_API_KEY')}, body)
        if data.get('code') or data.get('status_code', 200) != 200:
            raise TTSError('百炼业务错误；检查模型、区域、权限和额度，未自动重试。')
        audio = (data.get('output') or {}).get('audio') or {}
        # data 可能是裸 PCM，优先下载官方返回的完整 WAV，不能直接冒充 WAV。
        url = audio.get('url')
        if not url:
            raise TTSError('百炼未返回完整音频 URL；未保存可能为裸 PCM 的 data。')
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not (parsed.hostname or '').endswith('.aliyuncs.com') or parsed.username or parsed.password:
            raise TTSError('百炼音频下载 URL 不是官方 OSS 地址。')
        url = urllib.parse.urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))
        with request(url, {}) as response:
            return response.read(), model
    if args.provider == 'tencent':
        if args.model or args.style or args.speed != 1:
            raise TTSError('腾讯云不映射 --model/--style/--speed；语速请用 --tencent-speed（原生范围 -2–6，默认 0）。')
        speed = getattr(args, 'tencent_speed', 0)
        if not -2 <= speed <= 6:
            raise TTSError('腾讯云 --tencent-speed 范围 -2–6。')
        if len(text) > (500 if text.isascii() else 150):
            raise TTSError('腾讯云基础接口限 150 中文字符或 500 英文字符；混合文本按 150 字符保守限制，请先分段。')
        if not re.fullmatch(r'[0-9]+', args.voice) or int(args.voice) <= 0 or int(args.voice) == 200000000:
            raise TTSError('腾讯云 --voice 必须是正整数 VoiceType；一句话声音复刻未接入。')
        language = getattr(args, 'language', None) or 'zh-CN'
        if language not in ('zh-CN', 'en-US'):
            raise TTSError('腾讯云 --language 当前支持 zh-CN 或 en-US。')
        body = {'Text': text, 'SessionId': str(uuid.uuid4()), 'VoiceType': int(args.voice), 'ModelType': 1,
                'Codec': args.format, 'SampleRate': 16000, 'Speed': speed, 'PrimaryLanguage': 2 if language == 'en-US' else 1}
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        timestamp = int(time.time())
        headers = {'Content-Type': 'application/json; charset=utf-8', 'Host': 'tts.tencentcloudapi.com',
                   'X-TC-Action': 'TextToVoice', 'X-TC-Version': '2019-08-23', 'X-TC-Timestamp': str(timestamp),
                   'Authorization': tc3_authorization(payload, key('TENCENT_SECRET_ID'), key('TENCENT_SECRET_KEY'), timestamp)}
        if os.environ.get('TENCENT_REGION'):
            headers['X-TC-Region'] = os.environ['TENCENT_REGION']
        if os.environ.get('TENCENT_TOKEN'):
            headers['X-TC-Token'] = os.environ['TENCENT_TOKEN']
        data = load_json('https://tts.tencentcloudapi.com/', headers, payload)['Response']
        if data.get('Error'):
            raise TTSError('腾讯云业务错误；检查官方错误码、权限和额度，未自动重试。')
        return base64.b64decode(data.get('Audio', ''), validate=True), 'TextToVoice/2019-08-23'
    if args.provider == 'azure':
        if args.model or not 0.5 <= args.speed <= 2:
            raise TTSError('Azure 不使用 --model；--speed 范围 0.5–2。')
        if not re.fullmatch(r'[a-z]{2,3}-[A-Z]{2}-[A-Za-z0-9-]+', args.voice):
            raise TTSError('Azure --voice 应为官方 ShortName，例如 zh-CN-XiaoxiaoNeural。')
        language = getattr(args, 'language', None) or '-'.join(args.voice.split('-')[:2])
        if not re.fullmatch(r'[a-z]{2,3}-[A-Z]{2}', language):
            raise TTSError('Azure --language 应为 locale，例如 zh-CN。')
        root = ET.Element('speak', {'version': '1.0', 'xmlns': 'http://www.w3.org/2001/10/synthesis', 'xml:lang': language})
        voice = ET.SubElement(root, 'voice', {'name': args.voice})
        if args.style:
            rows = live_voices('azure')['voices']
            row = next((v for v in rows if v.get('ShortName') == args.voice), {})
            if args.style not in row.get('StyleList', []):
                raise TTSError('Azure 指定音色在当前区域不支持该 style；先查询 --live 的 StyleList。')
            root.set('xmlns:mstts', 'https://www.w3.org/2001/mstts')
            voice = ET.SubElement(voice, 'mstts:express-as', {'style': args.style})
        ET.SubElement(voice, 'prosody', {'rate': '%+.2f%%' % ((args.speed - 1) * 100)}).text = text
        headers = {'Ocp-Apim-Subscription-Key': key('AZURE_SPEECH_KEY'), 'Content-Type': 'application/ssml+xml',
                   'X-Microsoft-OutputFormat': 'audio-24khz-48kbitrate-mono-mp3' if args.format == 'mp3' else 'riff-24khz-16bit-mono-pcm', 'User-Agent': 'ALLTTS'}
        with request(azure_base() + '/cognitiveservices/v1', headers, ET.tostring(root, encoding='utf-8')) as response:
            return response.read(), 'Azure Speech neural'
    if args.provider == 'elevenlabs':
        if args.style or args.speed != 1:
            raise TTSError('ElevenLabs 此版不映射自由文本 --style/--speed；模型语速控制尚待单独验收。')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', args.voice):
            raise TTSError('ElevenLabs --voice 应填写 --live 返回的 voice_id。')
        if getattr(args, 'language', None):
            raise TTSError('ElevenLabs 此版不映射 --language；默认多语种模型自动识别文本。')
        model = args.model or 'eleven_multilingual_v2'
        body = {'text': text, 'model_id': model}
        with request('https://api.elevenlabs.io/v1/text-to-speech/' + urllib.parse.quote(args.voice, safe='') + '?output_format=mp3_44100_128', {'xi-api-key': key('ELEVENLABS_API_KEY'), 'Accept': 'audio/mpeg'}, body) as response:
            return response.read(), model
    raise TTSError('不支持的 P1 厂商。')

def synth_cloud(args, text):
    if args.provider in extra.PROVIDERS:
        return extra.synth(_client_context(), args, text)
    if args.provider in ('aliyun', 'tencent', 'azure', 'elevenlabs'):
        return synth_p1(args, text)
    if args.provider == 'minimax':
        known = [v for v in catalog('minimax') if v['id'] == args.voice]
        if known and not any(v.get('runnable', True) for v in known):
            raise TTSError('该 MiniMax ID 仅来自本地历史表，当前公开 API/模型映射未核实；先用账号音色列表核对。')
        if not 0.5 <= args.speed <= 2:
            raise TTSError('MiniMax 语速范围 0.5–2.0')
        if len(text) >= 10000:
            raise TTSError('MiniMax 同步接口文本需少于 10000 字符；长文请先分段。')
        region = os.environ.get('MINIMAX_REGION', 'cn')
        if region not in ('cn', 'global'):
            raise TTSError('MINIMAX_REGION 必须是 cn 或 global')
        host = 'https://api.minimax.cn' if region == 'cn' else 'https://api.minimax.io'
        model = args.model or 'speech-2.8-hd'
        body = {'model': model, 'text': text, 'stream': False, 'output_format': 'hex',
                'voice_setting': {'voice_id': args.voice, 'speed': args.speed, 'vol': 1, 'pitch': 0},
                'audio_setting': {'format': args.format, 'sample_rate': 24000, 'channel': 1}}
        if args.style:
            raise TTSError('MiniMax 此客户端未映射自由文本风格；请去掉 --style，或使用 Gemini。')
        data = load_json(host + '/v1/t2a_v2', {'Authorization': 'Bearer ' + key('MINIMAX_API_KEY')}, body)
        check_minimax(data)
        return bytes.fromhex((data.get('data') or {}).get('audio', '')), model
    if args.provider == 'volcengine':
        if not 0.5 <= args.speed <= 2:
            raise TTSError('火山语速范围 0.5–2.0')
        matching = [v for v in catalog('volcengine') if v['id'] == args.voice]
        if not matching or not any(v['runnable'] for v in matching):
            raise TTSError('该音色属于其他产品/模型；当前生成器只接入 seed-tts-2.0。')
        if args.model:
            raise TTSError('火山预置2.0音色无需 --model；当前脚本不实现声音复刻。')
        if args.style:
            raise TTSError('火山自由文本指令尚未在此客户端实现；请去掉 --style。')
        body = {'req_params': {'text': text, 'speaker': args.voice, 'audio_params': {'format': args.format, 'sample_rate': 24000, 'speech_rate': round((args.speed - 1) * 100)}}}
        headers = {'X-Api-Key': key('VOLCENGINE_API_KEY'), 'X-Api-Resource-Id': 'seed-tts-2.0', 'X-Api-Request-Id': str(uuid.uuid4())}
        with request('https://openspeech.bytedance.com/api/v3/tts/unidirectional', headers, body) as response:
            return decode_volc(response), 'seed-tts-2.0'
    if args.speed != 1:
        raise TTSError('Gemini 使用 --style 指定语速，不能机械映射 --speed。')
    model = args.model or 'gemini-3.8-flash-tts'
    content = {'type': 'text', 'text': text}
    if args.style:
        content['annotations'] = [{'type': 'speech_metadata', 'style': args.style}]
    body = {'model': model, 'input': [{'type': 'user_input', 'content': [content]}], 'response_format': {'type': 'audio'}, 'generation_config': {'speech_config': [{'voice': args.voice}]}}
    data = load_json('https://generativelanguage.googleapis.com/v1beta/interactions', {'x-goog-api-key': key('GEMINI_API_KEY')}, body)
    audio = data.get('output_audio') or data.get('outputAudio')
    if not audio:
        # REST output content 可包含 audio block，避免写出空结果。
        audio = next((v for v in data.get('outputs', []) if v.get('type') == 'audio'), None)
    if not audio:
        # 原始 REST 响应使用 steps[].content[]；output_audio 是 SDK 的便捷属性。
        blocks = [block for step in data.get('steps', []) if step.get('type') == 'model_output'
                  for block in step.get('content', []) if block.get('type') == 'audio']
        audio = blocks[-1] if blocks else None
    if not audio or not audio.get('data'):
        raise TTSError('Gemini 未返回音频；检查当前 Interactions 响应和模型支持。')
    return base64.b64decode(audio['data'], validate=True), model

def synth_system(args, text, destination):
    if args.model or args.style or args.speed != 1:
        raise TTSError('系统客户端暂不统一映射 model/style/speed；默认语速生成。')
    available = system_voices()
    if args.voice not in [v['id'] for v in available]:
        raise TTSError('本机未安装指定音色，请先运行 voices --provider system --live。')
    system = platform.system()
    with tempfile.TemporaryDirectory(prefix='alltts-') as tmp:
        source = Path(tmp) / 'input.txt'
        source.write_text(text, encoding='utf-8')
        if system == 'Darwin':
            run_local(['say', '-v', args.voice, '-f', str(source), '-o', str(destination)])
        elif system == 'Windows':
            env = dict(os.environ, ALLTTS_TEXT=str(source), ALLTTS_OUTPUT=str(destination), ALLTTS_VOICE=args.voice)
            powershell("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.SelectVoice($env:ALLTTS_VOICE); $s.SetOutputToWaveFile($env:ALLTTS_OUTPUT); $s.Speak([System.IO.File]::ReadAllText($env:ALLTTS_TEXT,[System.Text.Encoding]::UTF8)); $s.Dispose()", env)
        else:
            run_local(['espeak-ng', '-v', args.voice, '-f', str(source), '-w', str(destination)])
    return destination.read_bytes(), system

def validate_audio(data, fmt):
    if len(data) < 32:
        raise TTSError('音频为空或过短；未发布输出文件。')
    valid = {'wav': data.startswith(b'RIFF') and data[8:12] == b'WAVE',
             'aiff': data.startswith(b'FORM') and data[8:12] in (b'AIFF', b'AIFC'),
             'mp3': data.startswith(b'ID3') or any(data[i] == 255 and data[i+1] & 224 == 224 for i in range(min(len(data)-1, 4096)))}
    if not valid.get(fmt, False):
        raise TTSError('返回字节与音频格式不符；未发布输出文件。')

def generate(args):
    text = args.text if args.text is not None else Path(args.text_file).read_text(encoding='utf-8-sig')
    if not text.strip():
        raise TTSError('文稿不能为空')
    if getattr(args, 'language', None) and args.provider not in ('aliyun', 'tencent', 'azure', 'google', 'polly', 'cartesia'):
        raise TTSError('该厂商当前不映射 --language。')
    if getattr(args, 'tencent_speed', 0) != 0 and args.provider != 'tencent':
        raise TTSError('--tencent-speed 仅用于腾讯云。')
    for name, default, provider in (('xfyun_speed', 50, 'xfyun'), ('baidu_speed', 5, 'baidu')):
        if getattr(args, name, default) != default and args.provider != provider:
            raise TTSError('--' + name.replace('_', '-') + ' 仅用于 ' + provider)
    allowed = {p: ('mp3', 'wav') for p in extra.PROVIDERS}
    allowed.update({'aliyun': ('wav',), 'tencent': ('mp3', 'wav'), 'azure': ('mp3', 'wav'), 'elevenlabs': ('mp3',)})
    if args.provider in allowed and args.format not in allowed[args.provider]:
        raise TTSError('该厂商当前输出格式为 ' + '/'.join(allowed[args.provider]) + '；请对应设置 --format。')
    if args.provider == 'gemini' and args.format != 'wav':
        raise TTSError('Gemini 当前只输出 WAV，请使用 --format wav。')
    if args.provider == 'system':
        expected = 'aiff' if platform.system() == 'Darwin' else 'wav'
        if args.format != expected:
            raise TTSError('本机系统音频格式为 ' + expected + '；请对应设置 --format。')
    if args.provider in ('minimax', 'volcengine') and args.format != 'mp3':
        raise TTSError('当前 MiniMax/火山生成器只开放 MP3，避免流式 WAV 容器拼接问题。')
    dest = Path(args.output).expanduser().resolve()
    if dest.suffix.lower() != '.' + args.format:
        raise TTSError('输出文件扩展名必须与 --format 一致')
    if dest.exists() or dest.with_suffix(dest.suffix + '.json').exists():
        raise TTSError('输出或元数据文件已存在；请选择新文件名。')
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.alltts-', suffix='.' + args.format, dir=str(dest.parent))
    os.close(fd)
    tmp = Path(tmp)
    published_audio = False
    published_meta = False
    meta_dest = dest.with_suffix(dest.suffix + '.json')
    meta_tmp = None
    try:
        if args.provider == 'system':
            audio, model = synth_system(args, text, tmp)
        else:
            audio, model = synth_cloud(args, text)
        validate_audio(audio, args.format)
        tmp.write_bytes(audio)
        # 硬链接原子发布，不覆盖其他任务刚生成的同名文件。
        metadata = {'provider': args.provider, 'model': model, 'voice': args.voice, 'format': args.format, 'text_characters': len(text), 'bytes': len(audio), 'source': SOURCES[args.provider], 'verification': '容器头检查通过；尚需试听', 'output': str(dest)}
        fd, name = tempfile.mkstemp(prefix='.alltts-', suffix='.json', dir=str(dest.parent))
        meta_tmp = Path(name)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(redact(json.dumps(metadata, ensure_ascii=False, indent=2)) + '\n')
        os.link(str(tmp), str(dest))
        published_audio = True
        os.link(str(meta_tmp), str(meta_dest))
        published_meta = True
    except Exception:
        if published_audio:
            dest.unlink(missing_ok=True)
        if published_meta:
            meta_dest.unlink(missing_ok=True)
        raise
    else:
        emit(metadata)
    finally:
        tmp.unlink(missing_ok=True)
        if meta_tmp is not None:
            meta_tmp.unlink(missing_ok=True)

def recommend(args):
    data = json.loads((ROOT / 'references' / 'recommendations.json').read_text(encoding='utf-8'))
    items = [v for v in data if args.scene in v['scenes'] and (not args.provider or args.provider == v['provider'])]
    if args.language != 'zh-CN':
        raise TTSError('当前精选推荐面向普通话；其他语言请按官方目录过滤并试听，不套用普通话排名。')
    emit({'scene': args.scene, 'language': args.language, 'basis': '规则精选，不是质量排行榜；未在本次实测云音频', 'candidates': items[:args.limit]})

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    voices = sub.add_parser('voices', help='查询官方本地音色目录或账号实时目录')
    voices.add_argument('--provider', choices=PROVIDERS)
    voices.add_argument('--live', action='store_true')
    voices.add_argument('--query', default='')
    voices.add_argument('--model', help='筛选模型或 Polly engine，不会调用合成接口')
    voices.add_argument('--api-profile', help='筛选接口配置 ID，例如 xfyun.super.v1')
    voices.add_argument('--runnable-only', action='store_true', help='仅显示当前生成器支持的记录，仍须确认账号权限')
    voices.add_argument('--limit', type=int, default=0, help='0 为全部')
    rec = sub.add_parser('recommend', help='按中文创作场景推荐试听候选')
    rec.add_argument('--scene', choices=('knowledge','short-video','news','story','warm','ad'), required=True)
    rec.add_argument('--provider', choices=PROVIDERS[:3])
    rec.add_argument('--language', default='zh-CN')
    rec.add_argument('--limit', type=int, default=3)
    gen = sub.add_parser('generate', help='生成音频；调用用户配置的密钥，可能计费')
    gen.add_argument('--provider', choices=PROVIDERS, required=True)
    gen.add_argument('--voice', required=True)
    gen.add_argument('--model')
    group = gen.add_mutually_exclusive_group(required=True)
    group.add_argument('--text')
    group.add_argument('--text-file')
    gen.add_argument('--format', choices=('mp3','wav','aiff'), default='mp3')
    gen.add_argument('--speed', type=float, default=1)
    gen.add_argument('--style')
    gen.add_argument('--language', help='百炼用 Auto/Chinese/English；腾讯/Azure/Google/Polly 用语言代码；Cartesia 用 zh/en 等')
    gen.add_argument('--tencent-speed', type=float, default=0, help='腾讯原生 Speed：-2–6，0 为正常语速')
    gen.add_argument('--xfyun-speed', type=int, default=50, help='讯飞原生语速0–100，默认50')
    gen.add_argument('--baidu-speed', type=int, default=5, help='百度原生语速0–15，默认5')
    gen.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'voices':
            if args.live:
                if not args.provider:
                    raise TTSError('--live 需要指定 --provider')
                if args.query or args.limit or args.model or args.api_profile or args.runnable_only:
                    raise TTSError('--live 返回完整账号响应；过滤请保存 JSON 后处理。')
                emit(live_voices(args.provider))
            elif args.provider == 'system':
                emit({'scope':'本机实时音色','voices':system_voices()})
            else:
                rows = catalog(args.provider)
                rows = [v for v in rows if args.query.lower() in json.dumps(v,ensure_ascii=False).lower()]
                if args.model:
                    rows = [v for v in rows if args.model in (v.get('model') if isinstance(v.get('model'), list) else [v.get('model')])]
                if args.api_profile:
                    rows = [v for v in rows if args.api_profile in v.get('api_profiles', [])]
                if args.runnable_only:
                    rows = [v for v in rows if v.get('runnable', True)]
                shown = rows[:args.limit] if args.limit > 0 else rows
                profiles = json.loads((ROOT/'references/api-profiles.json').read_text(encoding='utf-8'))['profiles']
                used = {p for v in shown for p in v.get('api_profiles', [])}
                emit({'count':len(rows), 'unique_ids':len({v['id'] for v in rows}), 'voices':shown,
                      'api_profiles':{p:profiles[p] for p in sorted(used)},
                      'scope': '公开目录快照；账号目录厂商需指定 --provider 配合 --live 查询' if not args.provider else json.loads((ROOT / 'references' / (args.provider + '-voices.json')).read_text(encoding='utf-8')).get('scope', '官方公开目录快照，账号授权以控制台为准')})
        elif args.command == 'recommend':
            recommend(args)
        else:
            generate(args)
    except TTSError as e:
        print(redact('错误：' + str(e)), file=sys.stderr)
        return 1
    except Exception:
        # 任意解析/SDK/文件错误不打印原始响应、签名 URL、文稿或 traceback。
        print('错误：响应解析或本地操作失败；检查格式、参数和输出权限；未自动重试。', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())

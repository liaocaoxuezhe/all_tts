"""从官方快照重建扩展音色目录；Python 3.9 标准库，不调用合成接口。

原始 *-official.* 文件仅本机保存。目录按产品/模型分行，同一 ID 可以重复。
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import os
import tempfile
from pathlib import Path
from catalog_html import article, tables, expanded

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / 'skills/alltts/references'
RAW = ROOT / 'test'
DATE = '2026-10-11'
PROFILES = {}
OUTPUTS = {}


def profile(key, provider, product, endpoint, version, parameter, source, **extra):
    PROFILES[key] = dict(provider=provider, product=product, endpoint=endpoint,
                         api_version=version, voice_parameter=parameter, source=source,
                         verified_at=DATE, **extra)
    return key


MINIMAX = profile('minimax.http.v1', 'minimax', 'Speech HTTP',
    'https://api.minimax.cn/v1/t2a_v2', 'v1', 'voice_setting.voice_id',
    'https://platform.minimax.cn/docs/api-reference/speech-t2a-http',
    note='t2a_v2 是操作路径；speech-* 是模型版本。系统目录未逐音色声明全部模型兼容性，账号查询及实际授权优先。')
MINIMAX_ARCHIVE = profile('minimax.archive.unresolved', 'minimax', '2024 本地历史音色表，接口待核实',
    None, None, None, '20240620_Minimax 新增音色.xlsx',
    note='用户提供的历史表含星野提示，没有 API/模型版本信息；不推断可用于当前公开 Speech API。')
QWEN = profile('aliyun.qwen.http.v1', 'aliyun', 'Qwen-TTS 非实时',
    'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
    'v1', 'input.voice', 'https://help.aliyun.com/zh/model-studio/qwen-tts-api')
QWEN_RT = profile('aliyun.qwen.realtime.v1', 'aliyun', 'Qwen-TTS 实时',
    'wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}',
    'v1', 'session.voice', 'https://help.aliyun.com/zh/model-studio/qwen-tts-realtime')
COSY_HTTP = profile('aliyun.cosy.http.v1', 'aliyun', 'CosyVoice 非实时',
    'https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer',
    'v1', 'input.voice', 'https://help.aliyun.com/zh/model-studio/cosyvoice-tts-http-api')
COSY_WS = profile('aliyun.cosy.websocket.v1', 'aliyun', 'CosyVoice WebSocket',
    'wss://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference',
    'v1', 'payload.parameters.voice', 'https://help.aliyun.com/zh/model-studio/cosyvoice-websocket-api')
AUDIO = profile('aliyun.qwen_audio.http.v1', 'aliyun', 'Qwen-Audio-TTS 非实时',
    'https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer',
    'v1', 'input.voice', 'https://help.aliyun.com/zh/model-studio/qwen-audio-tts-http-api')
TC = profile('tencent.text_to_voice.2019-08-23', 'tencent', '基础语音合成',
    'https://tts.tencentcloudapi.com/', '2019-08-23', 'VoiceType',
    'https://cloud.tencent.com/document/api/1073/37995', action='TextToVoice')
TC_RT = profile('tencent.stream_ws', 'tencent', '实时语音合成',
    'wss://tts.cloud.tencent.com/stream_ws', None, 'VoiceType',
    'https://cloud.tencent.com/document/api/1073/94308', action='TextToStreamAudioWS',
    note='专用 WebSocket 协议，没有云 API Version 参数，不能套用 2019-08-23。')
TC_LONG = profile('tencent.long.2019-08-23', 'tencent', '长文本语音合成',
    'https://tts.tencentcloudapi.com/', '2019-08-23', 'VoiceType',
    'https://cloud.tencent.com/document/api/1073/57373', action='CreateTtsTask')
XF = profile('xfyun.online.v2', 'xfyun', '在线语音合成',
    'wss://tts-api.xfyun.cn/v2/tts', 'v2', 'business.vcn',
    'https://www.xfyun.cn/doc/tts/online_tts/API.html')
XF_SUPER = profile('xfyun.super.v1', 'xfyun', '超拟人语音合成',
    'wss://cbm01.cn-huabei-1.xf-yun.com/v1/private/mcd9m97e6', 'v1', 'parameter.tts.vcn',
    'https://www.xfyun.cn/doc/spark/super%20smart-tts.html',
    note='x6_* 是发音人代次，不是 /v6 接口；不可发送到在线 /v2/tts。')
XF_LONG = profile('xfyun.long.v1', 'xfyun', '长文本语音合成',
    'https://api-dx.xf-yun.com/v1/private/dts_create', 'v1', 'parameter.dts.vcn',
    'https://www.xfyun.cn/doc/tts/long_text_tts/API.html',
    query_endpoint='https://api-dx.xf-yun.com/v1/private/dts_query')
AZURE = profile('azure.speech.v1', 'azure', 'Speech SSML REST',
    'https://{region}.tts.speech.microsoft.com/cognitiveservices/v1', 'v1', 'SSML voice/@name',
    'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech',
    note='公开全球目录不是当前资源区域可用目录；ShortName 和 style 仍须 --live 核对。')
GOOGLE = profile('google.cloud.v1', 'google', 'Cloud Text-to-Speech',
    'https://texttospeech.googleapis.com/v1/text:synthesize', 'v1', 'voice.name',
    'https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize')
POLLY = profile('polly.speech.v1', 'polly', 'Amazon Polly',
    'https://polly.{region}.amazonaws.com/v1/speech', 'v1', 'VoiceId',
    'https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html',
    note='Engine 必须属于该条 supported_engines；区域仍须 DescribeVoices 确认。')
OPENAI = profile('openai.speech.v1', 'openai', 'Audio Speech',
    'https://api.openai.com/v1/audio/speech', 'v1', 'voice',
    'https://developers.openai.com/api/docs/guides/text-to-speech')
BAIDU = profile('baidu.short.text2audio', 'baidu', '短文本语音合成',
    'https://tsn.baidu.com/text2audio', None, 'per',
    'https://bce.bdstatic.com/p3m/pdf/ai-cloud-share/online/SPEECH/SPEECH.pdf',
    note='路径没有版本号；音库分类不是接口版本。')
GEMINI = profile('gemini.interactions.v1beta', 'gemini', 'Gemini Developer TTS',
    'https://generativelanguage.googleapis.com/v1beta/interactions', 'v1beta',
    'generation_config.speech_config[].voice', 'https://ai.google.dev/api/interactions-api',
    note='语音配置字段以当前客户端和官方 Interactions 文档为准；不等同 Google Cloud TTS。')
VOLC = profile('volcengine.tts.v3', 'volcengine', '豆包 TTS 2.0 HTTP',
    'https://openspeech.bytedance.com/api/v3/tts/unidirectional', 'v3', 'req_params.speaker',
    'https://docs.volcengine.com/docs/DoubaoVoice/unidirectional-streaming-text-to-speech-http?lang=zh',
    resource_id='seed-tts-2.0')
VOLC_PENDING = profile('volcengine.other.unresolved', 'volcengine', '其他产品表，资源映射待核实',
    None, None, None, 'https://docs.volcengine.com/docs/DoubaoVoice/Tonelist-1?lang=zh',
    note='保留已有跨产品音色；缺少已核实的资源及接口映射，不猜测可调用版本。')
profile('elevenlabs.tts.v1','elevenlabs','Text to speech',
    'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}','v1','URL voice_id',
    'https://elevenlabs.io/docs/api-reference/text-to-speech/convert',
    catalog_endpoint='https://api.elevenlabs.io/v2/voices',catalog_scope='账号分页目录，需要用户密钥，不预置公共库全部 ID')
profile('fish.tts.v1','fish','Fish Audio TTS','https://api.fish.audio/v1/tts','v1','reference_id',
    'https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech',
    catalog_endpoint='https://api.fish.audio/model',catalog_scope='当前工作空间自有模型分页，需密钥；模型版本由 model header 指定')
profile('cartesia.tts.2026-08-14','cartesia','Cartesia Bytes','https://api.cartesia.ai/tts/bytes',
    '2026-08-14','voice','https://docs.cartesia.ai/api-reference/tts/bytes',
    version_parameter='Cartesia-Version',catalog_endpoint='https://api.cartesia.ai/voices',
    catalog_scope='当前账号可见音色游标分页，需要用户密钥；API 日期与 sonic-* 模型版本分开')


def row(provider, voice_id, name, source, binding, model=None, runnable=False, **extra):
    return dict(provider=provider, id=voice_id, name=name, source=source, verified_at=DATE,
                api_profiles=[binding], model=model, runnable=runnable,
                account_scope='官方公开目录；未验证账号/区域开通权限，未云端合成实测', **extra)


def save(provider, voices, scope):
    if not voices: raise ValueError('空目录: ' + provider)
    data = dict(schema_version=2, verified_at=DATE, scope=scope,
                api_profiles_file='api-profiles.json', voices=voices)
    OUTPUTS[REF / (provider + '-voices.json')] = data
    print(provider, len(voices), 'records;', len({v['id'] for v in voices}), 'unique IDs')


def build_xfyun():
    source = PROFILES[XF]['source']
    voices = [row('xfyun', 'x4_xiaoyan', 'x4_xiaoyan', source, XF,
                  'online-tts/v2', True, official_description='在线接口 vcn 参数示例，权限须在控制台确认')]
    # 在线接口 FAQ 明确提及这六个 vcn；不借用 SDK/AIUI 的其他名单。
    text = article(RAW/'xfyun-online-official.html')
    for voice_id in ('xiaoyan', 'xiaoyu', 'xiaofeng', 'xiaoqi', 'catherine', 'mary'):
        if voice_id not in text: raise ValueError('在线文档不再列出: ' + voice_id)
        voices.append(row('xfyun', voice_id, voice_id, source, XF, 'online-tts/v2', True,
                          official_description='在线接口 FAQ 提及的发音人；支持及授权须在控制台确认'))
    super_rows = {}
    for table in tables(RAW/'xfyun-super-official.html'):
        header = [c['text'] for c in table['rows'][0]]
        if header[:2] != ['姓名', 'vcn']: continue
        for cells in list(expanded(table))[1:]:
            c = [x['text'] for x in cells]
            voice_id = c[1]
            if voice_id in super_rows:
                super_rows[voice_id]['default_free'] = True
                continue
            super_rows[voice_id] = row('xfyun', voice_id, c[0], PROFILES[XF_SUPER]['source'], XF_SUPER,
                'super-smart-tts', gender=c[2], language=c[3],
                official_description=c[4] if len(c)>4 else None,
                default_free=len(c)==4, product='超拟人语音合成')
    voices.extend(super_rows.values())
    for table in tables(RAW/'xfyun-long-official.html'):
        if [c['text'] for c in table['rows'][0]][:2] != ['中文名称', '参数名称（vcn=）']: continue
        for cells in list(expanded(table))[1:]:
            c = [x['text'] for x in cells]
            voices.append(row('xfyun', c[1], c[0], PROFILES[XF_LONG]['source'], XF_LONG,
                'long-text-tts', gender=c[2], language=c[3], official_description=c[4], product='长文本语音合成'))
    save('xfyun', voices, '在线文档候选 + 超拟人公开全表 + 长文本附录全表；各产品的 vcn 不互相推断兼容')


def build_azure_google():
    source = 'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts'
    voices = []
    for table in tables(RAW/'azure-official.html'):
        if table['heading'] != 'Text to speech voices': continue
        for cells in list(expanded(table))[1:]:
            c = [x['text'] for x in cells]
            ids = re.findall(r'\b[a-z]{2,3}-[A-Za-z0-9:-]+', c[3])
            if len(ids) != 1: raise ValueError(('Azure 音色列', c[3]))
            voice_id = ids[0]
            # 当前 Azure CLI ShortName 校验不接受带冒号的 HD 名称。
            runnable = bool(re.fullmatch(r'[a-z]{2,3}-[A-Z]{2}-[A-Za-z0-9-]+',voice_id))
            voices.append(row('azure', voice_id, voice_id, source, AZURE, c[2], runnable,
                language=c[0], language_name=c[1], gender=c[3].split('(')[-1].rstrip(')'),
                official_description=None, styles_roles=c[4], voice_conversion=c[5],
                support_note='区域及预览状态以实时列表为准；带冒号的 HD 音色当前 CLI 未接入'))
    save('azure', voices, '官方 Text to speech voices 全球表；不包含用户自定义音色，不代表区域授权')
    source = 'https://docs.cloud.google.com/text-to-speech/docs/voices'
    voices = []
    for table in tables(RAW/'google-official.html'):
        if [c['text'] for c in table['rows'][0]][:2] != ['Language', 'Voice type']: continue
        for cells in list(expanded(table))[1:]:
            c = [x['text'] for x in cells]
            family = c[3][len(c[2])+1:].rsplit('-',1)[0]
            voices.append(row('google', c[3], c[3], source, GOOGLE, family, True,
                language=c[2], language_name=c[0], voice_type=c[1], gender=c[4],
                official_description=None))
    save('google', voices, '官方支持语言完整表；Cloud TTS /v1，与 Gemini Developer API 分开')


def build_polly():
    source = 'https://docs.aws.amazon.com/polly/latest/dg/available-voices.html'
    api_text = re.sub('<[^>]+>', ' ', article(RAW/'polly-api-official.html'))
    enum = re.search(r'Valid Values:\s*(Aditi\s*\|.*?)Required: Yes', api_text, re.S)
    if not enum: raise ValueError('Polly VoiceId 枚举缺失')
    allowed = {v.strip() for v in enum[1].split('|')}
    voices = []
    for cells in list(expanded(tables(RAW/'polly-official.html')[0]))[1:]:
        c = [x['text'] for x in cells]
        ids = cells[3]['parts']
        genders = cells[4]['parts']
        engines = [x['parts'] for x in cells[5:9]]
        if any(len(x)!=len(ids) for x in [genders]+engines): raise ValueError(('Polly 列错位', c))
        for n, label in enumerate(ids):
            # 官方表使用带重音的显示名，API 枚举给出精确 VoiceId。
            candidates = [label.rstrip('*').split('/')[-1]]
            candidates.append(''.join(x for x in unicodedata.normalize('NFD', candidates[0]) if unicodedata.category(x)!='Mn'))
            voice_id = next((x for x in candidates if x in allowed), None)
            supported = [e for e, values in zip(('generative','long-form','neural','standard'),engines) if values[n]=='Yes']
            voices.append(row('polly', voice_id or candidates[0], label.rstrip('*'), source, POLLY,
                supported, voice_id is not None, language=c[2], language_name=c[1], gender=genders[n],
                supported_engines=supported, official_description=None,
                api_enum_verified=voice_id is not None, api_id_source=PROFILES[POLLY]['source'],
                support_note=None if voice_id else '显示名尚未出现在 API VoiceId 枚举，保留候选并停用生成'))
    save('polly', voices, '官方全语言表按音色展开；精确 ID 与 API 枚举交叉验证；保留引擎兼容矩阵')


def voice_info(text):
    match = re.search(r'名称\s*[：:]\s*(.+?)\s*voice\s*参数\s*[：:]\s*(.+?)(?=\s*(?:描述|特质|语言)\s*[：:])', text)
    if not match: raise ValueError(('阿里音色信息', text))
    lang = re.search(r'语言\s*[：:]\s*(.*)',text)
    desc = re.search(r'(?:描述|特质)\s*[：:]\s*(.*?)(?=\s*(?:年龄|性别|语言)\s*[：:]|$)',text)
    return dict(id=match[2].strip(),name=match[1].strip(),language=lang[1] if lang else None,
                official_description=desc[1].strip() if desc else None)


def xlsx_rows(path):
    ns = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        for r in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//m:sheetData/m:row',ns):
            cells = {}
            for c in r.findall('m:c',ns):
                letters = re.match('[A-Z]+',c.attrib['r'])[0]
                index=0
                for letter in letters:index=index*26+ord(letter)-64
                v=c.find('m:v',ns)
                value=v.text if v is not None else ''
                if c.get('t')=='s':value=strings[int(value)]
                if c.get('t')=='inlineStr':value=''.join(c.find('m:is',ns).itertext())
                cells[index-1]=value
            yield [cells.get(i,'') for i in range(max(cells,default=-1)+1)]


def build_aliyun():
    voices=[]
    for table in tables(RAW/'aliyun-qwen-official.html'):
        realtime = '非实时' not in table['heading']
        binding, model = (QWEN_RT,'qwen3-tts-flash-realtime') if realtime else (QWEN,'qwen3-tts-flash')
        for cells in list(expanded(table))[1:]:
            info = voice_info(cells[0]['text']);info['language']=cells[1]['text']
            voices.append(row('aliyun', info.pop('id'), info.pop('name'),
                'https://help.aliyun.com/zh/model-studio/qwen-tts-voice-list',binding,model,not realtime,**info))
    for table in tables(RAW/'aliyun-cosy-official.html'):
        model=table['heading']
        if not re.fullmatch('cosyvoice-v[0-9.]+(?:-(?:flash|plus))?',model):raise ValueError(model)
        for cells in list(expanded(table))[1:]:
            c=[x['text'] for x in cells];info=voice_info(c[1])
            v=row('aliyun',info.pop('id'),info.pop('name'),
                'https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list',COSY_WS,model,
                official_scenes=c[0],features=c[2],region=c[4],**info)
            if model!='cosyvoice-v1':v['api_profiles'].append(COSY_HTTP)
            voices.append(v)
    audio_source='https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list'
    for table in tables(RAW/'aliyun-audio-official.html'):
        direct='qwen-audio-' not in table['heading']
        model='qwen-audio-3.1-tts-flash' if direct else table['heading']
        for cells in list(expanded(table))[1:]:
            c=[x['text'] for x in cells]
            if direct:
                multi=table['heading']=='多语种与方言音色'
                english=table['heading']=='精品英文音色'
                info=dict(id=c[1],name=c[0],gender=c[2],language='多语种/方言（参见官方表）' if multi else ('英文' if english else '中文普通话'),
                    official_description=None if multi else c[3],official_scenes=c[4] if len(c)==6 else None)
            else:info=voice_info(c[1]);info['official_scenes']=c[0]
            voices.append(row('aliyun',info.pop('id'),info.pop('name'),audio_source,AUDIO,model,**info))
    for i,model in enumerate(('qwen-audio-3.0-tts-plus','qwen-audio-3.0-tts-flash')):
        rows=list(xlsx_rows(RAW/('aliyun-audio-%s-official.xlsx'%i)))
        if rows[0][:3]!=['序号','名称','voice参数']:raise ValueError('基础音色表结构变化')
        for n,c in enumerate(rows[1:],2):
            if not c or not c[2]:continue
            if not c[2].startswith(model+'-'):raise ValueError('基础音色模型错配: '+c[2])
            voices.append(row('aliyun',c[2],c[1],audio_source,AUDIO,model,gender=c[3],age=c[4],
                official_description=c[5],official_scenes=c[6],language=c[7],preview_filename=c[8],
                voice_category='基础复刻音色',source_sheet='Sheet1',source_row=n))
    save('aliyun',voices,'Qwen 非实时/实时 + CosyVoice 各模型 + Qwen-Audio 系统及官方 Excel 基础音色；按 ID/模型/接口分别保留')


def build_tencent():
    voices=[]
    for table in tables(RAW/'tencent-official.html'):
        if table['heading']=='实时语音合成音色列表':binding,model=TC_RT,'TextToStreamAudioWS'
        elif table['heading']=='基础语音合成音色列表':binding,model=TC,'TextToVoice/2019-08-23'
        elif table['heading']=='长文本语音合成音色列表':binding,model=TC_LONG,'CreateTtsTask/2019-08-23'
        else:raise ValueError(table['heading'])
        for cells in list(expanded(table))[1:]:
            c=[x['text'] for x in cells]
            if len(c)!=7 or not c[0].isdigit():raise ValueError(c)
            voices.append(row('tencent',c[0],c[1],'https://cloud.tencent.com/document/product/1073/92668',
                binding,model,binding==TC,official_description=c[2],voice_type=c[3],language=c[4],
                sample_rates=c[5],emotions=c[6],product=table['heading'],region='中国站'))
    save('tencent',voices,'实时、基础、长文本三个官方全表分别绑定协议；重复 ID 是跨产品支持记录')


def enrich_existing():
    for provider,binding in [('minimax',MINIMAX),('gemini',GEMINI),('openai',OPENAI),('baidu',BAIDU),('volcengine',VOLC)]:
        p=REF/(provider+'-voices.json');data=json.loads(p.read_text(encoding='utf-8'))
        if provider=='minimax':
            official=[]
            for line in (RAW/'minimax-official.html').read_text(encoding='utf-8').splitlines():
                c=[x.strip() for x in line.strip('|').split('|')]
                if len(c)==4 and c[0].isdigit():
                    official.append(row('minimax',c[2].strip('`'),c[3],
                        'https://platform.minimax.cn/docs/faq/system-voice-id.md',MINIMAX,None,True,
                        language=c[1],official_description=c[3],description_basis='官方名称，未补造年龄或音质特征',
                        model_compatibility='系统表未给出逐音色模型矩阵；账号 get_voice 与合成授权优先'))
            merge_minimax_archive(official,data['voices'])
            save(provider,official,'327 条当前官方系统音色 + 本地 2024 历史表缺失条目；历史条目的当前接口/模型未核实，runnable=false')
            continue
        data['schema_version']=2;data['api_profiles_file']='api-profiles.json'
        for v in data['voices']:
            mapped=binding
            if provider=='volcengine' and v['table_index']!=0:mapped=VOLC_PENDING
            v['api_profiles']=[mapped]
        OUTPUTS[p] = data


def merge_minimax_archive(official, previous):
    workbook=RAW/'20240620_Minimax 新增音色.xlsx'
    lookup={v['id']:v for v in official}
    for v in official:v['source_kind']='official'
    if not workbook.exists():
        # 仓库外的用户 Excel 不分发；重建时保留已归档资料。
        for v in previous:
            if v.get('source_kind')=='local_historical':
                if v['id'] in lookup:
                    lookup[v['id']]['historical_sources']=v.get('historical_sources',[])
                else:official.append(v)
            elif v['id'] in lookup and v.get('historical_sources'):
                lookup[v['id']]['historical_sources']=v['historical_sources']
        return
    rows=list(xlsx_rows(workbook))
    if rows[0][:2]!=['名称','性别'] or rows[0][4]!='Voice_id':raise ValueError('用户 Excel 列结构变化')
    matched,missing,same_names,skipped=[],[],[],[]
    seen=set()
    for n,c in enumerate(rows[1:],2):
        if len(c)<5 or not c[4]:skipped.append(n);continue
        if c[4] in seen:raise ValueError('历史表重复 ID: '+c[4])
        seen.add(c[4])
        local=dict(file=workbook.name,sheet='Sheet1',row=n,name=c[0],id=c[4],
                   gender=c[1],age_group=c[2],description=c[3],source_date='2024-06-20')
        if c[4] in lookup:
            lookup[c[4]]['historical_sources']=[local]
            matched.append(local)
        else:
            possible=[v['id'] for v in lookup.values() if v['name']==c[0]]
            if possible:same_names.append(dict(name=c[0],historical_id=c[4],official_ids=possible))
            v=row('minimax',c[4],c[0],workbook.name,MINIMAX_ARCHIVE,
                official_description=None,language=None,source_kind='local_historical',
                historical_sources=[local],local_description=c[3],gender=c[1],age_group=c[2],
                compatibility_status='当前公开 API/模型映射未核实',collected_at=DATE)
            v['verified_at']=None
            v['account_scope']='用户本地历史表；未核实当前 API 权限及模型适配'
            official.append(v);missing.append(local)
    import hashlib
    OUTPUTS[REF/'minimax-spreadsheet-audit.json']=dict(compared_at=DATE,source_file=workbook.name,
        source_sha256=hashlib.sha256(workbook.read_bytes()).hexdigest(),source_sheet='Sheet1',
        effective_ids=len(seen),original_official_matches=len(matched),original_missing=len(missing),
        skipped_rows=skipped,matched=matched,added_as_historical=missing,
        same_name_different_id=same_names,
        note='第 68 行是“星野音色id.xlsx”提示而非音色；名称相同不证明 ID 等价；原始 Excel 不改动、不分发。')


def main():
    build_xfyun()
    build_azure_google()
    build_polly()
    build_aliyun()
    build_tencent()
    enrich_existing()
    OUTPUTS[REF/'api-profiles.json'] = dict(schema_version=1,profiles=PROFILES)
    # 解析/校验全部成功后才发布，构建失败不会覆盖旧快照。
    for data in OUTPUTS.values():
        for voice in data.get('voices',[]):
            if not voice.get('id') or not voice.get('name'):raise ValueError('音色 ID/名称为空')
            for key in voice['api_profiles']:
                if key not in PROFILES or PROFILES[key]['provider']!=voice['provider']:raise ValueError('接口映射错误')
    pending=[]
    try:
        for dest,data in OUTPUTS.items():
            fd,name=tempfile.mkstemp(prefix='.alltts-catalog-',suffix='.json',dir=str(REF))
            with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
            pending.append((Path(name),dest))
        for temp,dest in pending:temp.replace(dest)
    finally:
        for temp,_ in pending:temp.unlink(missing_ok=True)


if __name__=='__main__':main()

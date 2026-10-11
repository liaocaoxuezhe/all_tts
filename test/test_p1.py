"""P1 官方协议与安全输出测试，全部离线，不调用计费接口。"""
import base64
import io
import json
import os
import tempfile
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import test_alltts as p0
from test_alltts import client, ROOT, MP3, WAV

class P1Test(unittest.TestCase):
    args = p0.ClientTest.args
    def test_tc3_official_golden_vector(self):
        # 官方签名 v3 示例，使用文档中的星号占位凭据。
        payload = b'{"Limit": 1, "Filters": [{"Values": ["\\u672a\\u547d\\u540d"], "Name": "instance-name"}]}'
        result = client.tc3_authorization(payload, 'AKID********************************', '********************************', 1551113065, 'cvm.tencentcloudapi.com', 'cvm', 'DescribeInstances')
        self.assertTrue(result.endswith('Signature=10b1a37a7301a02ca19a647ad722d5e43b4b3cff309d421d85b46093f6ab6c4f'))
        self.assertIn('/2019-02-25/cvm/', result)

    def test_tencent_utf8_signature_and_decode(self):
        requests = []
        def open_request(req, timeout):
            requests.append(req)
            return io.BytesIO(json.dumps({'Response': {'Audio': base64.b64encode(WAV).decode()}}).encode())
        with patch.dict(os.environ, {'TENCENT_SECRET_ID': 'test-id', 'TENCENT_SECRET_KEY': 'test-secret'}), patch.object(client.time, 'time', return_value=1551113065), patch.object(client.HTTP, 'open', open_request):
            audio, _ = client.synth_cloud(self.args('tencent', voice='101001', format='wav', tencent_speed=1.25), '中文& English')
        req = requests[0]
        self.assertEqual(audio, WAV)
        self.assertEqual(json.loads(req.data)['VoiceType'], 101001)
        self.assertEqual(json.loads(req.data)['Speed'], 1.25)
        self.assertIn('中文', req.data.decode('utf-8'))
        self.assertEqual(req.get_header('Authorization'), client.tc3_authorization(req.data, 'test-id', 'test-secret', 1551113065))
        self.assertEqual(req.get_header('X-tc-version'), '2019-08-23')

    def test_tencent_business_error(self):
        with patch.dict(os.environ, {'TENCENT_SECRET_ID': 'test-id', 'TENCENT_SECRET_KEY': 'test-secret'}), patch.object(client, 'load_json', return_value={'Response': {'Error': {'Code': 'AuthFailure', 'Message': 'private transcript'}}}):
            with self.assertRaises(client.TTSError) as err:
                client.synth_cloud(self.args('tencent', voice='101001'), '中文')
        self.assertNotIn('private transcript', str(err.exception))

    def test_tencent_guards_before_network(self):
        for values in (dict(voice='Adam'), dict(voice='200000000'), dict(voice='101001', tencent_speed=7), dict(voice='101001', speed=1.2)):
            with self.subTest(values=values), patch.object(client, 'load_json') as call:
                with self.assertRaises(client.TTSError): client.synth_cloud(self.args('tencent', **values), '中文')
                call.assert_not_called()
        with self.assertRaises(client.TTSError): client.synth_cloud(self.args('tencent', voice='101001'), '中'*151)

    def test_aliyun_region_body_and_wav_download(self):
        calls = []
        def open_request(req, timeout):
            calls.append(req)
            if len(calls) == 1: return io.BytesIO(json.dumps({'output': {'audio': {'url': 'http://result.oss-cn-beijing.aliyuncs.com/a.wav?Signature=test', 'data': 'raw-pcm'}}}).encode())
            return io.BytesIO(WAV)
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY': 'test-key', 'DASHSCOPE_REGION': 'intl'}), patch.object(client.HTTP, 'open', open_request):
            audio, model = client.synth_cloud(self.args('aliyun', voice='Cherry', format='wav', language='Chinese'), '你好')
        self.assertEqual(audio, WAV)
        self.assertEqual(model, 'qwen3-tts-flash')
        self.assertIn('dashscope-intl.aliyuncs.com', calls[0].full_url)
        self.assertEqual(json.loads(calls[0].data)['input'], {'text':'你好', 'voice':'Cherry', 'language_type':'Chinese'})
        self.assertTrue(calls[1].full_url.startswith('https://'))
        self.assertIsNone(calls[1].get_header('Authorization'))

    def test_aliyun_errors_and_no_pcm_disguised_as_wav(self):
        responses = [{'code':'InvalidApiKey'}, {'output':{'audio':{'data':base64.b64encode(b'raw pcm').decode()}}}, {'output':{'audio':{'url':'https://example.test/a.wav'}}}]
        for response in responses:
            with self.subTest(response=response), patch.dict(os.environ, {'DASHSCOPE_API_KEY':'test-key', 'DASHSCOPE_REGION':'cn'}), patch.object(client,'load_json',return_value=response):
                with self.assertRaises(client.TTSError): client.synth_cloud(self.args('aliyun',voice='Cherry',format='wav'), '中文')

    def test_aliyun_model_voice_and_length_guards(self):
        for values, text in [(dict(model='cosyvoice-v3-flash',voice='Cherry'),'中文'), (dict(voice='made-up'),'中文'), (dict(voice='Cherry'),'中'*601)]:
            with self.subTest(values=values), patch.object(client,'load_json') as call:
                with self.assertRaises(client.TTSError): client.synth_cloud(self.args('aliyun',format='wav',**values),text)
                call.assert_not_called()

    def test_azure_ssml_escapes_text_and_style(self):
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY':'test-key','AZURE_SPEECH_REGION':'eastasia'}), patch.object(client,'live_voices',return_value={'voices':[{'ShortName':'zh-CN-XiaoxiaoNeural','StyleList':['cheerful']}]}), patch.object(client,'request',return_value=io.BytesIO(WAV)) as call:
            audio, _ = client.synth_cloud(self.args('azure',voice='zh-CN-XiaoxiaoNeural',format='wav',style='cheerful',speed=1.2), '你好 <break/> & "世界"')
        url, headers, body = call.call_args.args
        self.assertEqual(audio,WAV)
        self.assertEqual(headers['Content-Type'],'application/ssml+xml')
        self.assertEqual(headers['X-Microsoft-OutputFormat'],'riff-24khz-16bit-mono-pcm')
        xml = ET.fromstring(body)
        prosody = xml.find('.//{http://www.w3.org/2001/10/synthesis}prosody')
        self.assertEqual(prosody.text,'你好 <break/> & "世界"')
        self.assertEqual(prosody.attrib['rate'],'+20.00%')
        self.assertIn('eastasia.tts.speech.microsoft.com',url)

    def test_azure_invalid_style_before_synthesis(self):
        with patch.object(client,'live_voices',return_value={'voices':[]}), patch.object(client,'request') as call:
            with self.assertRaises(client.TTSError): client.synth_cloud(self.args('azure',voice='zh-CN-XiaoxiaoNeural',style='not-supported'), '中文')
            call.assert_not_called()

    def test_azure_live_preserves_official_fields(self):
        rows=[{'ShortName':'zh-CN-XiaoxiaoNeural','StyleList':['cheerful'],'Locale':'zh-CN'}]
        with patch.dict(os.environ, {'AZURE_SPEECH_KEY':'test-key','AZURE_SPEECH_REGION':'eastasia'}), patch.object(client,'load_json',return_value=rows) as call:
            result=client.live_voices('azure')
        self.assertEqual(result['voices'],rows)
        self.assertTrue(call.call_args.args[0].endswith('/cognitiveservices/voices/list'))

    def test_elevenlabs_binary_request(self):
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY':'test-key'}), patch.object(client,'request',return_value=io.BytesIO(MP3)) as call:
            audio, model=client.synth_cloud(self.args('elevenlabs',voice='exact_account_id'), '中文')
        self.assertEqual(audio,MP3)
        self.assertEqual(model,'eleven_multilingual_v2')
        self.assertIn('/exact_account_id?output_format=mp3_44100_128',call.call_args.args[0])
        self.assertEqual(call.call_args.args[1]['xi-api-key'],'test-key')

    def test_elevenlabs_full_pagination_and_descriptions(self):
        pages=[{'voices':[{'voice_id':'a','description':'中文描述','labels':{'language':'zh'}}],'has_more':True,'next_page_token':'second page'}, {'voices':[{'voice_id':'b'}],'has_more':False,'next_page_token':'unused'}]
        with patch.dict(os.environ, {'ELEVENLABS_API_KEY':'test-key'}), patch.object(client,'load_json',side_effect=pages) as call:
            rows=client.live_voices('elevenlabs')['voices']
        self.assertEqual([v['voice_id'] for v in rows],['a','b'])
        self.assertEqual(rows[0]['description'],'中文描述')
        self.assertIn('next_page_token=second+page',call.call_args.args[0])

    def test_elevenlabs_missing_or_repeated_token_stops(self):
        for response in ({'voices':[], 'has_more':True}, {'voices':[], 'has_more':True,'next_page_token':'same'}):
            with self.subTest(response=response), patch.dict(os.environ, {'ELEVENLABS_API_KEY':'test-key'}), patch.object(client,'load_json',return_value=response):
                with self.assertRaises(client.TTSError): client.live_voices('elevenlabs')

    def test_p1_http_error_and_timeout_no_retry(self):
        for error in (urllib.error.HTTPError('https://example.test',401,'Unauthorized',{},None), urllib.error.URLError('timeout')):
            for provider, voice, fmt, env in [('aliyun','Cherry','wav',{'DASHSCOPE_API_KEY':'test-key','DASHSCOPE_REGION':'cn'}),('tencent','101001','mp3',{'TENCENT_SECRET_ID':'test-id','TENCENT_SECRET_KEY':'test-key'}),('azure','zh-CN-XiaoxiaoNeural','mp3',{'AZURE_SPEECH_KEY':'test-key','AZURE_SPEECH_REGION':'eastasia'}),('elevenlabs','account_id','mp3',{'ELEVENLABS_API_KEY':'test-key'})]:
                with self.subTest(provider=provider,error=error), patch.dict(os.environ,env), patch.object(client.HTTP,'open',side_effect=error) as call:
                    with self.assertRaises(client.TTSError): client.synth_cloud(self.args(provider,voice=voice,format=fmt),'中文')
                    self.assertEqual(call.call_count,1)

    def test_empty_or_invalid_audio_no_output(self):
        for provider, fmt in [('aliyun','wav'),('tencent','mp3'),('azure','wav'),('elevenlabs','mp3')]:
            for audio in (b'', b'{"error":"failed"}'):
                with self.subTest(provider=provider,audio=audio), tempfile.TemporaryDirectory(dir=str(ROOT/'test')) as directory:
                    dest=Path(directory)/('output.'+fmt)
                    with patch.object(client,'synth_cloud',return_value=(audio,'test')):
                        with self.assertRaises(client.TTSError): client.generate(self.args(provider,format=fmt,output=str(dest)))
                    self.assertEqual(list(Path(directory).iterdir()),[])

    def test_format_rejected_before_cloud_call(self):
        for provider, fmt in [('aliyun','mp3'),('elevenlabs','wav'),('azure','aiff'),('tencent','aiff')]:
            with self.subTest(provider=provider), patch.object(client,'synth_cloud') as call:
                with self.assertRaises(client.TTSError): client.generate(self.args(provider,format=fmt))
                call.assert_not_called()

    def test_p1_credentials_redacted(self):
        names=['DASHSCOPE_API_KEY','TENCENT_SECRET_ID','TENCENT_SECRET_KEY','TENCENT_TOKEN','AZURE_SPEECH_KEY','ELEVENLABS_API_KEY']
        with patch.dict(os.environ,{n:'test-'+n for n in names}):
            result=client.redact(' '.join('test-'+n for n in names))
        self.assertEqual(result,' '.join('[REDACTED]' for _ in names))

    def test_p1_catalogs_and_live_only_guidance(self):
        for provider in ('aliyun','tencent'):
            rows=client.catalog(provider)
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(row['provider'],provider)
                self.assertTrue(row['source'].startswith('https://'))
                self.assertIn('official_description',row)
                self.assertIn('account_scope',row)
        self.assertTrue(client.catalog('azure'))
        for provider in ('elevenlabs','fish','cartesia'):
            with self.assertRaises(client.TTSError): client.catalog(provider)

if __name__ == '__main__': unittest.main()

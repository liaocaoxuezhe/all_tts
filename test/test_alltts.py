"""协议、输出完整性及推荐引用测试；不会调用计费API。"""
import argparse
import base64
import importlib.util
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('alltts', ROOT / 'skills/alltts/scripts/alltts.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
MP3 = b'ID3' + b'\0' * 100
WAV = b'RIFF' + b'\0' * 4 + b'WAVE' + b'\0' * 100

class ClientTest(unittest.TestCase):
    def args(self, provider='minimax', **values):
        defaults = dict(provider=provider, voice='Chinese (Mandarin)_Radio_Host', model=None, text='中文文稿', text_file=None, speed=1, style=None, format='mp3', output='unused.mp3')
        defaults.update(values)
        return argparse.Namespace(**defaults)

    def test_minimax_hex_and_utf8_request(self):
        calls = []
        def urlopen(req, timeout):
            calls.append(req)
            return io.BytesIO(json.dumps({'base_resp':{'status_code':0},'data':{'audio':MP3.hex()}}).encode())
        with patch.dict(os.environ, {'MINIMAX_API_KEY':'test-only-key','MINIMAX_REGION':'cn'}), patch.object(client.HTTP, 'open', urlopen):
            audio, model = client.synth_cloud(self.args(), '你好，知识内容。')
        self.assertEqual(audio, MP3)
        self.assertEqual(json.loads(calls[0].data.decode('utf-8'))['text'], '你好，知识内容。')
        self.assertEqual(calls[0].get_header('Authorization'), 'Bearer test-only-key')

    def test_minimax_business_error(self):
        with patch.object(client, 'load_json', return_value={'base_resp':{'status_code':1004}}), patch.dict(os.environ, {'MINIMAX_API_KEY':'test-only-key'}):
            with self.assertRaises(client.TTSError):
                client.synth_cloud(self.args(), '中文')

    def test_volc_stream_json_and_sse(self):
        lines = [json.dumps({'code':0,'data':base64.b64encode(MP3[:40]).decode()}).encode()+b'\n', b'data: '+json.dumps({'code':0,'data':base64.b64encode(MP3[40:]).decode()}).encode()+b'\n']
        self.assertEqual(client.decode_volc(iter(lines)), MP3)

    def test_volc_error_after_partial_audio(self):
        lines = [json.dumps({'code':0,'data':base64.b64encode(MP3).decode()}).encode(), b'{"code":45000001}']
        with self.assertRaises(client.TTSError):
            client.decode_volc(iter(lines))

    def test_volc_resource_and_speech_rate(self):
        with patch.dict(os.environ, {'VOLCENGINE_API_KEY':'test-only-key'}), patch.object(client, 'request', return_value=io.BytesIO(b'{"code":0,"data":"'+base64.b64encode(MP3)+b'"}\n')) as request:
            audio, model = client.synth_cloud(self.args('volcengine', voice='zh_female_vv_uranus_bigtts', speed=1.2), '中文')
        self.assertEqual(audio, MP3)
        self.assertEqual(request.call_args.args[1]['X-Api-Resource-Id'], 'seed-tts-2.0')
        self.assertEqual(request.call_args.args[2]['req_params']['audio_params']['speech_rate'], 20)

    def test_reject_s2s_voice_for_tts(self):
        with self.assertRaises(client.TTSError):
            client.synth_cloud(self.args('volcengine', voice='zh_female_vv_jupiter_bigtts'), '中文')

    def test_gemini_wav_not_double_wrapped(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-only-key'}), patch.object(client, 'load_json', return_value={'output_audio':{'data':base64.b64encode(WAV).decode()}}) as request:
            audio, model = client.synth_cloud(self.args('gemini', voice='Charon', style='自然普通话', format='wav'), '中文')
        self.assertEqual(audio, WAV)
        body = request.call_args.args[2]
        self.assertEqual(body['input'][0]['content'][0]['text'], '中文')
        self.assertEqual(body['input'][0]['content'][0]['annotations'][0]['style'], '自然普通话')

    def test_gemini_rest_audio_block(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-only-key'}), patch.object(client, 'load_json', return_value={'outputs':[{'type':'audio','data':base64.b64encode(WAV).decode()}]}):
            audio, _ = client.synth_cloud(self.args('gemini', voice='Charon', format='wav'), '中文')
        self.assertEqual(audio, WAV)

    def test_gemini_all_pages(self):
        responses = [{'voices':[{'id':'a'}],'next_page_token':'second'}, {'voices':[{'id':'b'}]}]
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-only-key'}), patch.object(client, 'load_json', side_effect=responses) as request:
            data = client.live_voices('gemini')
        self.assertEqual([x['id'] for x in data['voices']], ['a','b'])
        self.assertIn('page_token=second', request.call_args.args[0])

    def test_repeat_page_token_stops(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-only-key'}), patch.object(client, 'load_json', return_value={'voices':[],'next_page_token':'same'}):
            with self.assertRaises(client.TTSError):
                client.live_voices('gemini')

    def test_http_error_does_not_echo_key_or_transcript(self):
        err = urllib.error.HTTPError('https://example.test', 401, 'Unauthorized', {}, io.BytesIO(b'test-only-secret private transcript'))
        with patch.object(client.HTTP, 'open', side_effect=err):
            with self.assertRaises(client.TTSError) as caught:
                client.request('https://example.test', {})
        self.assertNotIn('test-only-secret', str(caught.exception))
        self.assertNotIn('private transcript', str(caught.exception))

    def test_failed_audio_never_published(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT/'test')) as directory:
            dest = Path(directory)/'bad.mp3'
            with patch.object(client,'synth_cloud',return_value=(b'{}','test')):
                with self.assertRaises(client.TTSError):
                    client.generate(self.args(output=str(dest)))
            self.assertFalse(dest.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_publish_metadata_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=str(ROOT/'test')) as directory:
            dest = Path(directory)/'中文.mp3'
            with patch.object(client,'synth_cloud',return_value=(MP3,'test')), patch.object(client,'emit'):
                client.generate(self.args(output=str(dest)))
                with self.assertRaises(client.TTSError):
                    client.generate(self.args(output=str(dest)))
            self.assertEqual(dest.read_bytes(),MP3)
            meta=json.loads(dest.with_suffix('.mp3.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['text_characters'],4)
            self.assertNotIn('中文文稿',json.dumps(meta,ensure_ascii=False))

    def test_recommendations_resolve_to_runnable_official_ids(self):
        rec=json.loads((client.ROOT/'references/recommendations.json').read_text(encoding='utf-8'))
        for item in rec:
            voices=[v for v in client.catalog(item['provider']) if v['id']==item['id']]
            self.assertTrue(voices, item['id'])
            self.assertTrue(any(v.get('runnable',True) for v in voices))
            self.assertTrue(item['official_source'].startswith('https://'))

    def test_minimax_10000_character_guard(self):
        with self.assertRaises(client.TTSError):
            client.synth_cloud(self.args(),'中'*10000)

    def test_format_validation(self):
        client.validate_audio(WAV,'wav')
        with self.assertRaises(client.TTSError):
            client.validate_audio(WAV,'mp3')

if __name__ == '__main__':
    unittest.main()

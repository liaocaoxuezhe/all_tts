"""其余7家协议、分页、SDK以及失败清理测试；不调用云接口。"""
import base64
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import test_alltts as p0
from test_alltts import client, MP3, WAV, ROOT

extra = client.extra
ENV = {'OPENAI_API_KEY':'test-openai', 'FISH_API_KEY':'test-fish', 'GOOGLE_ACCESS_TOKEN':'test-google',
       'GOOGLE_QUOTA_PROJECT':'test-project', 'XFYUN_API_KEY':'test-xf-key', 'XFYUN_API_SECRET':'test-xf-secret',
       'XFYUN_APP_ID':'test-app', 'BAIDU_API_KEY':'test-baidu', 'BAIDU_SECRET_KEY':'test-secret',
       'CARTESIA_API_KEY':'test-cartesia', 'AWS_REGION':'us-east-1', 'AWS_ACCESS_KEY_ID':'test-access',
       'AWS_SECRET_ACCESS_KEY':'test-aws-secret', 'AWS_SESSION_TOKEN':'test-token'}

class RemainingTest(unittest.TestCase):
    args = p0.ClientTest.args

    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_openai_utf8_model_style_format(self):
        with patch.object(client, 'request', return_value=io.BytesIO(WAV)) as req:
            audio, model = client.synth_cloud(self.args('openai',voice='marin',format='wav',style='自然中文',speed=1.2),'你好&世界')
        self.assertEqual(audio,WAV)
        self.assertEqual(model,'gpt-4o-mini-tts')
        url, headers, body=req.call_args.args
        self.assertEqual(url,'https://api.openai.com/v1/audio/speech')
        self.assertEqual(body,dict(model=model,input='你好&世界',voice='marin',response_format='wav',speed=1.2,instructions='自然中文'))
        self.assertEqual(headers['Authorization'],'Bearer test-openai')

    def test_openai_legacy_and_input_guards(self):
        for values,text in [(dict(voice='marin',model='tts-1'),'中文'),(dict(voice='alloy',model='tts-1',style='轻柔'),'中文'),(dict(voice='marin'),'中'*4097),(dict(voice='marin',speed=float('nan')),'中文')]:
            with self.subTest(values=values),patch.object(client,'request') as req:
                with self.assertRaises(client.TTSError):client.synth_cloud(self.args('openai',**values),text)
                req.assert_not_called()

    def test_fish_binary_protocol(self):
        with patch.object(client,'request',return_value=io.BytesIO(MP3)) as req:
            audio,model=client.synth_cloud(self.args('fish',voice='account_reference'),'中文')
        self.assertEqual(audio,MP3)
        self.assertEqual(req.call_args.args[1]['model'],'s2.1-pro')
        self.assertEqual(req.call_args.args[2],dict(text='中文',reference_id='account_reference',format='mp3'))

    def test_fish_self_scope_pagination(self):
        pages=[{'items':[{'_id':'v1','description':'官方描述'}],'has_more':True}, {'items':[{'_id':'v2'}],'has_more':False}]
        with patch.object(client,'load_json',side_effect=pages) as req:
            data=client.live_voices('fish')
        self.assertEqual(len(data['voices']),2)
        self.assertEqual(data['voices'][0]['description'],'官方描述')
        q=urllib.parse.parse_qs(urllib.parse.urlsplit(req.call_args.args[0]).query)
        self.assertEqual(q['page_number'],['2'])
        self.assertEqual(q['self'],['true'])

    def test_fish_incomplete_and_repeat_pages(self):
        for pages in [[{'items':[], 'has_more':True}], [{'items':[{'_id':'v'}],'has_more':True}]*2, [{'items':[{'_id':'v'}],'window_limited':True,'has_more':False}]]:
            with patch.object(client,'load_json',side_effect=pages),self.assertRaises(client.TTSError):client.live_voices('fish')

    def test_google_response_body_language_and_rate(self):
        with patch.object(client,'load_json',return_value={'audioContent':base64.b64encode(WAV).decode()}) as req:
            audio,_=client.synth_cloud(self.args('google',voice='cmn-CN-Wavenet-A',format='wav',speed=1.1),'中文')
        self.assertEqual(audio,WAV)
        body=req.call_args.args[2]
        self.assertEqual(body['voice']['languageCode'],'cmn-CN')
        self.assertEqual(body['audioConfig'],{'audioEncoding':'LINEAR16','speakingRate':1.1})
        self.assertEqual(req.call_args.args[1]['x-goog-user-project'],'test-project')

    def test_google_chirp_default_omits_rate(self):
        with patch.object(client,'load_json',return_value={'audioContent':base64.b64encode(MP3).decode()}) as req:
            client.synth_cloud(self.args('google',voice='en-US-Chirp3-HD-Achird'),'hi')
        self.assertNotIn('speakingRate',req.call_args.args[2]['audioConfig'])
        with self.assertRaises(client.TTSError):client.synth_cloud(self.args('google',voice='en-US-Chirp3-HD-Achird',speed=1.1),'hi')

    def test_google_limit_error_and_directory(self):
        with self.assertRaises(client.TTSError):client.synth_cloud(self.args('google'),'中'*1667)
        with patch.object(client,'load_json',return_value={'error':{'message':'private'}}),self.assertRaises(client.TTSError):client.synth_cloud(self.args('google'),'中文')
        with patch.object(client,'load_json',return_value={'voices':[{'name':'cmn-CN-Standard-A','languageCodes':['cmn-CN']}]}):
            self.assertEqual(client.live_voices('google')['voices'][0]['languageCodes'],['cmn-CN'])

    def test_cartesia_new_version_voice_string_and_format(self):
        with patch.object(client,'request',return_value=io.BytesIO(WAV)) as req:
            client.synth_cloud(self.args('cartesia',voice='account-id',format='wav',language='zh',speed=1.3),'中文')
        _,headers,body=req.call_args.args
        self.assertEqual(headers['Cartesia-Version'],'2026-08-14')
        self.assertEqual(headers['Authorization'],'Bearer test-cartesia')
        self.assertEqual(body['voice'],'account-id')
        self.assertEqual(body['output_format'],{'container':'wav','sample_rate':44100,'encoding':'pcm_s16le'})
        self.assertEqual(body['model_id'],'sonic-3.6')

    def test_cartesia_pagination(self):
        pages=[{'data':[{'id':'v1'}],'has_more':True,'next_page':'cursor'}, {'data':[{'id':'v2'}],'has_more':False}]
        with patch.object(client,'load_json',side_effect=pages) as req:
            self.assertEqual(len(client.live_voices('cartesia')['voices']),2)
        self.assertIn('starting_after=cursor',req.call_args.args[0])
        with patch.object(client,'load_json',return_value=pages[0]),self.assertRaises(client.TTSError):client.live_voices('cartesia')

    def test_xfyun_signature_fixed_vector(self):
        url=extra.xfyun_url('test-key','test-secret',1564624401)
        q=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(q['date'],['Thu, 01 Aug 2019 01:53:21 GMT'])
        expected='41Bw1kA4NpZwjHLokjfu5NP17grY5aGqo8Bm6A0P1VE='
        auth=base64.b64decode(q['authorization'][0]).decode()
        self.assertIn('signature="'+expected+'"',auth)

    def ws_module(self,frames):
        ws=Mock();ws.handshake_response.status=101;ws.recv.side_effect=frames
        return SimpleNamespace(create_connection=Mock(return_value=ws)),ws

    def test_xfyun_utf8_null_frames_and_pcm_wav(self):
        pcm=b'\0\0'*100
        module,ws=self.ws_module([json.dumps({'code':0,'data':None}),json.dumps({'code':0,'data':{'audio':base64.b64encode(pcm[:100]).decode(),'status':1}}),json.dumps({'code':0,'data':{'audio':base64.b64encode(pcm[100:]).decode(),'status':2}})])
        with patch.dict(sys.modules,{'websocket':module}):
            audio,_=client.synth_cloud(self.args('xfyun',voice='x4_xiaoyan',format='wav',xfyun_speed=60),'你好')
        with wave.open(io.BytesIO(audio)) as wav:
            self.assertEqual(wav.getframerate(),16000)
            self.assertEqual(wav.readframes(100),pcm)
        body=json.loads(ws.send.call_args.args[0])
        self.assertEqual(base64.b64decode(body['data']['text']).decode(),'你好')
        self.assertEqual(body['business']['tte'],'UTF8')
        ws.close.assert_called_once()

    def test_xfyun_error_and_incomplete_stream_close(self):
        for frame in [json.dumps({'code':11200,'message':'private'}),'',TimeoutError(),'{bad json']:
            module,ws=self.ws_module([frame])
            with patch.dict(sys.modules,{'websocket':module}),self.assertRaises(client.TTSError) as err:
                client.synth_cloud(self.args('xfyun'),'中文')
            self.assertNotIn('private',str(err.exception));ws.close.assert_called_once()

    def test_xfyun_utf8_byte_limit(self):
        with self.assertRaises(client.TTSError):client.synth_cloud(self.args('xfyun'),'中'*2667)

    def test_baidu_token_form_double_encoding_and_wav(self):
        class Audio(io.BytesIO):headers={'Content-Type':'audio/wav'}
        with patch.object(client,'load_json',return_value={'access_token':'returned-token'}) as token,patch.object(client,'request',return_value=Audio(WAV)) as req:
            audio,_=client.synth_cloud(self.args('baidu',voice='0',format='wav',baidu_speed=7),'你好 1+1=2 &%')
        self.assertEqual(audio,WAV)
        self.assertEqual(urllib.parse.parse_qs(token.call_args.args[2].decode())['client_id'],['test-baidu'])
        body=urllib.parse.parse_qs(req.call_args.args[2].decode())
        self.assertEqual(urllib.parse.unquote(body['tex'][0]),'你好 1+1=2 &%')
        self.assertEqual(body['aue'],['6']);self.assertEqual(body['tok'],['returned-token'])

    def test_baidu_token_business_error_and_gbk_limit(self):
        with patch.object(client,'load_json',return_value={'error':'invalid_client'}),self.assertRaises(client.TTSError):client.synth_cloud(self.args('baidu',voice='0'),'中文')
        class Bad(io.BytesIO):headers={'Content-Type':'application/json'}
        with patch.object(client,'load_json',return_value={'access_token':'test'}),patch.object(client,'request',return_value=Bad(b'{"err_no":500}')),self.assertRaises(client.TTSError):client.synth_cloud(self.args('baidu',voice='0'),'中文')
        for text in ['中'*512,'emoji😀']:
            with self.assertRaises(client.TTSError):client.synth_cloud(self.args('baidu',voice='0'),text)

    def test_polly_sdk_no_retry_and_explicit_credentials(self):
        import boto3
        with patch.object(boto3,'client',return_value=Mock()) as factory:
            extra.polly_client(client._client_context())
        kw=factory.call_args.kwargs
        self.assertEqual(kw['config'].retries,{'total_max_attempts':1})
        self.assertEqual(kw['aws_session_token'],'test-token')
        self.assertEqual(kw['region_name'],'us-east-1')

    def test_polly_sdk_stubber_mp3_and_pcm(self):
        from botocore.stub import Stubber
        for fmt,raw in [('mp3',MP3),('wav',b'\0\0'*100)]:
            api=extra.polly_client(client._client_context())
            params={'Text':'中文','TextType':'text','VoiceId':'Zhiyu','Engine':'standard','OutputFormat':'mp3' if fmt=='mp3' else 'pcm','SampleRate':'24000' if fmt=='mp3' else '16000'}
            stream=io.BytesIO(raw)
            with Stubber(api) as stub,patch.object(extra,'polly_client',return_value=api):
                stub.add_response('synthesize_speech',{'AudioStream':stream},params)
                audio,_=client.synth_cloud(self.args('polly',voice='Zhiyu',format=fmt),'中文')
                stub.assert_no_pending_responses()
            self.assertTrue(stream.closed)
            client.validate_audio(audio,fmt)

    def test_polly_sdk_pagination_and_error(self):
        api=Mock();api.describe_voices.side_effect=[{'Voices':[{'Id':'Zhiyu','SupportedEngines':['standard']}],'NextToken':'next'}, {'Voices':[]}]
        with patch.object(extra,'polly_client',return_value=api):
            self.assertEqual(len(client.live_voices('polly')['voices']),1)
        api.describe_voices.assert_called_with(NextToken='next');api.close.assert_called_once()
        api=Mock();api.synthesize_speech.side_effect=Exception('private signed url')
        with patch.object(extra,'polly_client',return_value=api),self.assertRaises(client.TTSError) as err:client.synth_cloud(self.args('polly',voice='Zhiyu'),'中文')
        self.assertNotIn('private',str(err.exception));api.close.assert_called_once()

    def test_all_providers_failure_cleanup(self):
        for provider in extra.PROVIDERS:
            fmt='mp3'
            with tempfile.TemporaryDirectory(dir=ROOT/'test') as tmp,patch.object(extra,'synth',return_value=(b'', 'test')):
                output=Path(tmp)/'中文.mp3'
                with self.assertRaises(client.TTSError):client.generate(self.args(provider,output=str(output)))
                self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_all_providers_http_timeout_and_error_no_retry(self):
        for provider,voice in [('openai','marin'),('fish','reference'),('google','cmn-CN-Wavenet-A'),('cartesia','id'),('baidu','0')]:
            for error in [urllib.error.HTTPError('https://test',403,'private',{},None),TimeoutError()]:
                with patch.object(client.HTTP,'open',side_effect=error) as req,self.assertRaises(client.TTSError):client.synth_cloud(self.args(provider,voice=voice),'中文')
                req.assert_called_once()

    def test_redaction_and_static_catalogs(self):
        for name,value in ENV.items():
            if name not in ('AWS_REGION','GOOGLE_QUOTA_PROJECT'):
                self.assertNotIn(value,client.redact('secret '+value))
        self.assertEqual(len(client.catalog('openai')),13)
        self.assertGreater(len(client.catalog('baidu')),4)
        self.assertEqual(client.catalog('xfyun')[0]['id'],'x4_xiaoyan')

if __name__ == '__main__':unittest.main()

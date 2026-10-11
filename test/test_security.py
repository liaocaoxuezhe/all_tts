"""发布前安全与真实 REST 结构回归测试，不调用云接口。"""
import base64
import io
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch
import test_alltts as p0
from test_alltts import client, MP3, WAV, ROOT

class SecurityTest(unittest.TestCase):
    args = p0.ClientTest.args

    def test_redirect_never_forwards_credentials(self):
        req = urllib.request.Request('https://example.test', headers={'Authorization': 'Bearer dummy'})
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code=code), self.assertRaises(client.TTSError):
                client.NoRedirect().redirect_request(req, None, code, '', {}, 'https://other.test')
        self.assertTrue(any(isinstance(h, client.NoRedirect) for h in client.HTTP.handlers))

    def test_insecure_or_embedded_credentials_url_rejected_before_network(self):
        for url in ('http://example.test', 'https://user:pass@example.test'):
            with self.subTest(url=url), patch.object(client.HTTP, 'open') as call:
                with self.assertRaises(client.TTSError):
                    client.request(url, {})
                call.assert_not_called()

    def test_encoded_and_stripped_credentials_redacted_from_stdout(self):
        secret = 'dummy-key/+ value'
        with patch.dict(os.environ, {'OPENAI_API_KEY': ' ' + secret + ' '}), patch('sys.stdout', new_callable=io.StringIO) as out:
            client.emit({'raw': secret, 'url': client.urllib.parse.quote(secret, safe='')})
        self.assertNotIn(secret, out.getvalue())
        self.assertNotIn('dummy-key', out.getvalue())
        self.assertEqual(json.loads(out.getvalue()), {'raw': '[REDACTED]', 'url': '[REDACTED]'})

    def test_unexpected_error_has_no_traceback_or_response(self):
        argv = ['alltts', 'voices', '--provider', 'minimax', '--live']
        with patch('sys.argv', argv), patch.object(client, 'live_voices', side_effect=AttributeError('private transcript dummy-secret')), patch('sys.stderr', new_callable=io.StringIO) as err:
            self.assertEqual(client.main(), 1)
        self.assertNotIn('private transcript', err.getvalue())
        self.assertNotIn('dummy-secret', err.getvalue())
        self.assertNotIn('Traceback', err.getvalue())

    def test_gemini_official_raw_rest_steps(self):
        response = {'steps': [{'type': 'model_output', 'content': [{'type': 'audio', 'data': base64.b64encode(WAV).decode()}]}]}
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'dummy-gemini'}), patch.object(client, 'load_json', return_value=response) as call:
            audio, _ = client.synth_cloud(self.args('gemini', voice='Charon', format='wav'), '中文')
        self.assertEqual(audio, WAV)
        self.assertEqual(call.call_args.args[2]['response_format'], {'type': 'audio'})

    def test_metadata_failure_rolls_back_only_our_audio(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test') as directory:
            dest = Path(directory)/'中文.mp3'
            meta = dest.with_suffix('.mp3.json')
            link = os.link
            def racing_link(src, target):
                if Path(target) == meta:
                    meta.write_text('另一任务的数据', encoding='utf-8')
                return link(src, target)
            with patch.object(client, 'synth_cloud', return_value=(MP3, 'dummy')), patch.object(client.os, 'link', side_effect=racing_link):
                with self.assertRaises(FileExistsError):
                    client.generate(self.args(output=str(dest)))
            self.assertFalse(dest.exists())
            self.assertEqual(meta.read_text(encoding='utf-8'), '另一任务的数据')
            self.assertEqual(list(Path(directory).iterdir()), [meta])

    def test_metadata_write_error_publishes_nothing(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test') as directory:
            dest = Path(directory)/'中文.mp3'
            with patch.object(client, 'synth_cloud', return_value=(MP3, 'dummy')), patch.object(client.json, 'dumps', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    client.generate(self.args(output=str(dest)))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_xfyun_redirect_does_not_send_transcript(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock
        ws = Mock()
        ws.handshake_response.status = 302
        connect = Mock(return_value=ws)
        env = {'XFYUN_API_KEY': 'dummy-key', 'XFYUN_API_SECRET': 'dummy-secret', 'XFYUN_APP_ID': 'dummy-app'}
        with patch.dict(os.environ, env), patch.dict(sys.modules, {'websocket': SimpleNamespace(create_connection=connect)}):
            with self.assertRaises(client.TTSError):
                client.synth_cloud(self.args('xfyun', voice='xiaoyan'), '私人文稿')
        self.assertEqual(connect.call_args.kwargs['redirect_limit'], 0)
        ws.send.assert_not_called()
        ws.close.assert_called_once()

    def test_polly_ignores_endpoint_override(self):
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'AWS_ACCESS_KEY_ID': 'dummy-access', 'AWS_SECRET_ACCESS_KEY': 'dummy-secret', 'AWS_ENDPOINT_URL': 'https://other.test', 'AWS_ENDPOINT_URL_POLLY': 'https://other.test'}):
            api = client.extra.polly_client(client._client_context())
            try:
                self.assertEqual(api.meta.endpoint_url, 'https://polly.us-east-1.amazonaws.com')
            finally:
                api.close()

if __name__ == '__main__':
    unittest.main()

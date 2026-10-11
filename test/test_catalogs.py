"""目录关系及跨协议误调用保护；不访问网络、不依赖原始 HTML/Excel。"""
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_alltts as base
import build_voice_catalogs as builder
from catalog_html import Tables, expanded
from test_alltts import client, ROOT


class CatalogTest(unittest.TestCase):
    args=base.ClientTest.args

    def test_profiles_resolve_and_products_stay_separate(self):
        profiles=json.loads((ROOT/'skills/alltts/references/api-profiles.json').read_text(encoding='utf-8'))['profiles']
        for v in client.catalog():
            with self.subTest(provider=v['provider'],voice=v['id']):
                self.assertTrue(v['api_profiles'])
                for key in v['api_profiles']:
                    self.assertEqual(profiles[key]['provider'],v['provider'])
                if v.get('runnable',True):
                    self.assertTrue(all(profiles[key]['endpoint'] for key in v['api_profiles']))
        self.assertEqual(profiles['xfyun.super.v1']['api_version'],'v1')
        self.assertIsNone(profiles['tencent.stream_ws']['api_version'])
        self.assertEqual(profiles['tencent.long.2019-08-23']['action'],'CreateTtsTask')

    def test_wrong_product_never_reaches_network(self):
        for provider,voice in [('xfyun','x6_lingxiaoxuan_pro'),('xfyun','x4_yeting'),
                               ('minimax','tiaopi_gongzhu'),('aliyun','longanyang')]:
            with self.subTest(provider=provider,voice=voice),patch.object(client,'request') as request,patch.object(client,'load_json') as load:
                with self.assertRaises(client.TTSError):client.synth_cloud(self.args(provider,voice=voice),'中文')
                request.assert_not_called();load.assert_not_called()

    def test_polly_engine_mismatch_precedes_sdk(self):
        with patch.object(client.extra,'polly_client') as sdk:
            with self.assertRaises(client.TTSError):client.synth_cloud(self.args('polly',voice='Hiujin',model='standard'),'中文')
            with self.assertRaises(client.TTSError):client.synth_cloud(self.args('polly',voice='Patrick',model='long-form'),'hi')
            sdk.assert_not_called()
        zhiyu=next(v for v in client.catalog('polly') if v['id']=='Zhiyu')
        self.assertEqual(zhiyu['supported_engines'],['neural','standard'])
        celine=next(v for v in client.catalog('polly') if v['id']=='Celine')
        self.assertTrue(celine['api_enum_verified'])

    def test_excel_reconciliation_keeps_provenance(self):
        audit=json.loads((ROOT/'skills/alltts/references/minimax-spreadsheet-audit.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['effective_ids'],audit['original_official_matches']+audit['original_missing'])
        rows={v['id']:v for v in client.catalog('minimax')}
        for item in audit['matched']:
            self.assertEqual(rows[item['id']]['source_kind'],'official')
            self.assertIn(item,rows[item['id']]['historical_sources'])
        for item in audit['added_as_historical']:
            v=rows[item['id']]
            self.assertFalse(v['runnable']);self.assertIsNone(v['official_description'])
            self.assertEqual(v['api_profiles'],['minimax.archive.unresolved'])
            self.assertEqual(v['local_description'],item['description'])

    def test_cli_filters_and_includes_endpoint(self):
        script=ROOT/'skills/alltts/scripts/alltts.py'
        result=json.loads(subprocess.check_output([sys.executable,str(script),'voices','--provider','aliyun',
            '--model','qwen3-tts-flash','--runnable-only','--limit','1'],text=True,encoding='utf-8'))
        self.assertEqual(result['count'],result['unique_ids'])
        self.assertEqual(result['voices'][0]['model'],'qwen3-tts-flash')
        self.assertEqual(result['api_profiles']['aliyun.qwen.http.v1']['voice_parameter'],'input.voice')

    def test_missing_local_workbook_preserves_archive_and_new_official_match(self):
        rows=client.catalog('minimax')
        fresh=[dict(v) for v in rows if v['source_kind']=='official']
        for v in fresh:v.pop('historical_sources',None)
        adopted=next(dict(v) for v in rows if v['id']=='tiaopi_gongzhu')
        adopted.update(source_kind='official',runnable=True)
        adopted.pop('historical_sources')
        fresh.append(adopted)
        with tempfile.TemporaryDirectory(dir=str(ROOT/'test')) as temp,patch.object(builder,'RAW',builder.Path(temp)):
            builder.merge_minimax_archive(fresh,rows)
        self.assertEqual({v['id'] for v in fresh},{v['id'] for v in rows})
        self.assertEqual(len(fresh),len(rows))
        self.assertTrue(adopted['runnable'])
        self.assertTrue(adopted['historical_sources'])
        self.assertTrue(next(v for v in fresh if v['id']=='qiaopi_mengmei')['historical_sources'])

    def test_rowspan_keeps_language_and_model_columns_aligned(self):
        parser=Tables()
        parser.feed('<h2>voices</h2><table><tr><th>language</th><th>id</th><th>model</th></tr>'
            '<tr><td rowspan="2">zh-CN</td><td>A</td><td rowspan="2">neural</td></tr>'
            '<tr><td>B</td></tr></table>')
        rows=[[c['text'] for c in r] for r in expanded(parser.tables[0])]
        self.assertEqual(rows[1:],[['zh-CN','A','neural'],['zh-CN','B','neural']])


if __name__=='__main__':unittest.main()

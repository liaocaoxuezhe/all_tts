"""从 test/ 中保存的官方 HTML 构建可追溯快照；不调用合成 API。"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None
    def handle_starttag(self, tag, attrs):
        if tag == 'tr': self.row = []
        if tag in ('td', 'th'): self.cell = []
    def handle_data(self, data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            if self.row is not None: self.row.append(' '.join(self.cell).strip())
            self.cell = None
        if tag == 'tr' and self.row:
            self.rows.append(self.row)
            self.row = None

def build(provider, filename, source):
    parser = Tables()
    parser.feed((ROOT/'test'/filename).read_text(encoding='utf-8'))
    voices = []
    for cells in parser.rows:
        if provider == 'aliyun':
            if len(cells) != 4 or 'qwen3-tts-flash-realtime' in cells[3] or 'qwen3-tts-flash' not in cells[3]: continue
            match = re.fullmatch(r'名称\s*：(.+?)\s*voice\s*参数\s*：(.+?)\s*描述\s*：(.+)', cells[0])
            if not match: raise ValueError(cells)
            row = dict(id=match[2].strip(), name=match[1].strip(), official_description=match[3].strip(), language=cells[1], model='qwen3-tts-flash', region=['cn', 'intl'])
        else:
            if not cells[0].isdigit(): continue
            if len(cells) != 7: raise ValueError(cells)
            row = dict(id=cells[0], name=cells[1], official_description=cells[2], voice_type=cells[3], language=cells[4], sample_rates=cells[5], emotions=cells[6], model='TextToVoice/2019-08-23', region='中国站')
        row.update(provider=provider, source=source, verified_at='2026-10-10', account_scope='公开系统音色表；未验证账号开通权限', runnable=True)
        voices.append(row)
    if not voices: raise ValueError('目录为空')
    # 官方页面可能按产品表重复展示同一音色，保留不同说明记录。
    voices = list({json.dumps(v, sort_keys=True, ensure_ascii=False): v for v in voices}.values())
    output = ROOT/'skills/alltts/references'/(provider+'-voices.json')
    output.write_text(json.dumps(dict(source=source, verified_at='2026-10-10', scope='官方公开表，未云端实测', voices=voices), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(provider, len(voices))

if __name__ == '__main__':
    build('aliyun', 'qwen-official.html', 'https://help.aliyun.com/zh/model-studio/qwen-tts-voice-list')
    build('tencent', 'tencent-official.html', 'https://cloud.tencent.com/document/product/1073/92668')

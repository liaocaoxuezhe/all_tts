"""下载公开官方目录到本机 test/；不读取密钥，不调用合成 API。"""
import concurrent.futures
import gzip
import re
from pathlib import Path
from urllib.request import Request, urlopen
from catalog_html import article

RAW=Path(__file__).resolve().parent
SOURCES={
    'xfyun-online':'https://www.xfyun.cn/doc/tts/online_tts/API.html',
    'xfyun-super':'https://www.xfyun.cn/doc/spark/super%20smart-tts.html',
    'xfyun-long':'https://www.xfyun.cn/doc/tts/long_text_tts/API.html',
    'azure':'https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts',
    'google':'https://docs.cloud.google.com/text-to-speech/docs/voices',
    'polly':'https://docs.aws.amazon.com/polly/latest/dg/available-voices.html',
    'polly-api':'https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html',
    'aliyun-qwen':'https://help.aliyun.com/zh/model-studio/qwen-tts-voice-list',
    'aliyun-cosy':'https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list',
    'aliyun-audio':'https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list',
    'tencent':'https://cloud.tencent.com/document/product/1073/92668',
    'minimax':'https://platform.minimax.cn/docs/faq/system-voice-id.md',
}


def download(url):
    with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=45) as response:
        data=response.read()
    if data.startswith(b'\x1f\x8b'):data=gzip.decompress(data)
    if not data:raise ValueError('空官方资料: '+url)
    return data


def main():
    # 任何下载失败都不触发目录重建；旧 references/ 保持不变。
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures={key:pool.submit(download,url) for key,url in SOURCES.items()}
        results={key:future.result() for key,future in futures.items()}
    for key,data in results.items():
        (RAW/(key+'-official.html')).write_bytes(data)
    links=re.findall(r'href="([^"]+\.xlsx[^" ]*)"',article(RAW/'aliyun-audio-official.html'))
    if len(links)!=2:raise ValueError('Qwen-Audio 基础音色附件数量变化，请人工核查')
    for i,url in enumerate(links):
        (RAW/('aliyun-audio-%s-official.xlsx'%i)).write_bytes(download(url))
    print('公开官方资料下载完成；运行 python3 test/build_voice_catalogs.py 重建。')


if __name__=='__main__':main()

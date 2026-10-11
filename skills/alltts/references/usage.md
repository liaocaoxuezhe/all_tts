# 配置与调用

核查日期：2026-10-10。Python 3.9+；基础客户端无 pip 依赖，Polly/讯飞使用下文的可选依赖。若以后增加 SDK，先检查其 Requires-Python；需要更高版本时应在对应 Python 版本的虚拟环境安装，单独创建 3.9 venv 不会提升解释器版本。

## 用户自己配置密钥

只设置需要的厂商，无需全部配置。密钥通过本机终端或宿主应用的安全环境注入；不要提交真实密钥。

| 厂商 | 环境变量 | 说明 |
|---|---|---|
| MiniMax | `MINIMAX_API_KEY` | 默认中国站 api.minimax.cn；国际站设置 `MINIMAX_REGION=global`，使用对应账号密钥 |
| 火山 | `VOLCENGINE_API_KEY` | 新版控制台 API Key 管理；当前实现用 X-Api-Key，不要求旧 App ID/Access Token |
| Gemini | `GEMINI_API_KEY` | Google AI Studio/项目 API Key，需具备模型和地区访问权限 |
| 百炼 | `DASHSCOPE_API_KEY`，可选 `DASHSCOPE_REGION` | cn（默认北京）或 intl（新加坡），密钥必须与地区匹配；仅 qwen3-tts-flash |
| 腾讯云 | `TENCENT_SECRET_ID`、`TENCENT_SECRET_KEY` | 中国站；可选 `TENCENT_REGION`；临时凭证需 `TENCENT_TOKEN` |
| Azure Speech | `AZURE_SPEECH_KEY`、`AZURE_SPEECH_REGION` | 公有云资源区域，例如 eastasia；区域与 Key 配套 |
| ElevenLabs | `ELEVENLABS_API_KEY` | 需具备音色查询和 TTS 权限 |
| 系统 | 无 | 枚举本机已安装音色；Linux 需已安装 espeak-ng |

终端可使用 `read -s` 交互输入，然后 `export` 变量，避免把真实密钥写进 shell 历史。例如在 zsh 中：

```bash
read -s 'MINIMAX_API_KEY?请输入 MiniMax API Key: '
export MINIMAX_API_KEY
```

若 Codex 和终端不是同一个进程环境，需要在实际执行客户端的环境配置变量。CLI 不自动加载 `.env`，不扫描其他项目凭证。

## 查询

项目根目录执行，移到其他位置时调整脚本路径：

```bash
python3 skills/alltts/scripts/alltts.py voices --provider minimax --query 电台
python3 skills/alltts/scripts/alltts.py voices --provider volcengine --query 磁性 --limit 10
python3 skills/alltts/scripts/alltts.py voices --provider gemini
python3 skills/alltts/scripts/alltts.py voices --provider minimax --live
python3 skills/alltts/scripts/alltts.py voices --provider gemini --live
python3 skills/alltts/scripts/alltts.py voices --provider system --live
python3 skills/alltts/scripts/alltts.py voices --provider aliyun --query 知识
python3 skills/alltts/scripts/alltts.py voices --provider tencent --query 解说
python3 skills/alltts/scripts/alltts.py voices --provider azure --live
python3 skills/alltts/scripts/alltts.py voices --provider elevenlabs --live
python3 skills/alltts/scripts/alltts.py recommend --scene knowledge --provider minimax
```

MiniMax 实时返回当前账号系统/克隆/设计音色和描述；未激活克隆音色可能不在列表。Gemini 遍历所有返回页，但仍限于该项目可见范围；它的扩展音色不能用 30 个预置音色名单代表。火山实时列表未实现，请在控制台确认权限。`--live` 不做本地 query/limit 过滤，完整返回数据便于保存和审查。

## 生成

```bash
python3 skills/alltts/scripts/alltts.py generate --provider minimax \
  --voice 'Chinese (Mandarin)_Radio_Host' --text '今天，我们来解释一个容易被误解的概念。' \
  --output out/minimax-demo.mp3

python3 skills/alltts/scripts/alltts.py generate --provider volcengine \
  --voice zh_male_cixingjieshuonan_uranus_bigtts --text-file 文稿.txt \
  --speed 1.05 --output out/volcengine-demo.mp3

python3 skills/alltts/scripts/alltts.py generate --provider gemini \
  --voice Charon --format wav --style '清晰自然的普通话知识讲解，语速适中，避免夸张的播音腔。' \
  --text-file 文稿.txt --output out/gemini-demo.wav
```

默认模型：MiniMax `speech-2.8-hd`；火山资源 `seed-tts-2.0`；Gemini `gemini-3.8-flash-tts`。MiniMax/Gemini 可显式传 `--model`，需先检查当前官方支持。中国与国际 MiniMax 站点的可用版本可能不同，不自动降级。

当前功能边界：单人文本转音频；没有长文自动分段/拼接、声音克隆、音色设计、字幕、双人配音、流式播放 UI。火山内部消费 HTTP 流并输出完整 MP3；Gemini 非流式 WAV 直接保存，不能重复加 WAV 头。输出必须使用新文件名，已有文件不会被覆盖。

## P1 生成示例与参数

```bash
python3 skills/alltts/scripts/alltts.py generate --provider aliyun \
  --voice Cherry --language Chinese --format wav --text '你好，这是一段中文试听。' --output out/aliyun.wav

python3 skills/alltts/scripts/alltts.py generate --provider tencent \
  --voice 101001 --tencent-speed 0 --text '你好，这是一段中文试听。' --output out/tencent.mp3

python3 skills/alltts/scripts/alltts.py generate --provider azure \
  --voice zh-CN-XiaoxiaoNeural --speed 1.1 --format wav \
  --text '你好，这是一段中文试听。' --output out/azure.wav

# 将账号查询返回的真实 voice_id 写入此变量，不能用音色显示名代替。
python3 skills/alltts/scripts/alltts.py generate --provider elevenlabs \
  --voice "$ELEVENLABS_VOICE_ID" --text '你好，这是一段中文试听。' --output out/elevenlabs.mp3
```

百炼默认 `qwen3-tts-flash`，只接受其48个官方系统音色；600字符上限，`--language` 为 Auto（默认）、Chinese、English 等官方语种值。下载完整WAV，不把可能为裸PCM的 audio.data 冒充WAV；无 `--style/--speed` 映射，未接 CosyVoice/Qwen-Audio-TTS/实时/克隆或工作空间专属端点。

腾讯 `--voice` 是整数 VoiceType；固定16kHz，MP3/WAV。150中文字符或500 ASCII字符，混合文本保守按150限制。`--tencent-speed` 使用原生刻度 -2–6，0正常、1约1.2倍、2约1.5倍；不映射通用 `--speed`。`--language` 支持 zh-CN（默认）或 en-US。未接长文、克隆和情感控制。

Azure 使用实时列表中的 ShortName；`--language` 默认从音色ID提取 locale。`--speed` 0.5–2 映射 SSML 相对速率；`--style` 必须属于该音色在区域目录中的 StyleList，客户端先查询再合成。文稿按纯文本转义，不直接解释为SSML。MP3为24kHz/48kbps单声道，WAV为24kHz/16bit单声道。官方REST音频超过10分钟会截断，长文请分段。只接公有云预置音色。

ElevenLabs 先运行 `voices --provider elevenlabs --live` 获取账号可见ID、描述和试听URL。默认 `eleven_multilingual_v2`，可用 `--model` 指定账号可用TTS模型；输出 `mp3_44100_128`，只开放MP3。此版不映射自由文本style、speed和language。账号目录不是全部共享Voice Library。

四家均通过离线协议测试，未进行真实云端合成或账号查询，也未进行音质评估。精选推荐仍覆盖原P0三家；P1按官方目录选候选并试听，不沿用未实测排名。

## 系统区别

| 系统 | 枚举 | 合成 | 输出 | 限制 |
|---|---|---|---|---|
| macOS | `say -v '?'` | `say -v 音色 -f UTF8文稿 -o 文件` | AIFF | 实际安装/下载音色因版本而异；命令支持的音色范围不等同 Siri/所有 AVSpeech 音色 |
| Windows | System.Speech `GetInstalledVoices()` | SpeechSynthesizer | WAV | 使用 Windows PowerShell 和已安装 SAPI 音色；不是 Azure 神经音色，也不等同全部 OneCore 音色 |
| Linux | `espeak-ng --voices` | espeak-ng | WAV | Linux 没有统一预装语音服务；未安装则清晰报错，不能称“系统自带” |

macOS 示例：先查真实列表，再选择可用中文音色。不要硬编码所有 Mac 都有 Tingting。

```bash
python3 skills/alltts/scripts/alltts.py generate --provider system \
  --voice Tingting --format aiff --text '你好，这是一段中文试听。' --output out/system-demo.aiff
```

正式交付可用 FFmpeg 转 WAV/MP3（须本机已安装），保留原文件；`ffprobe`/可解码性检查与试听才可补足容器头检查的局限。

## 剩余公开 API（2026-10-11）

新增 `openai`、`fish`、`xfyun`、`google`、`polly`、`baidu`、`cartesia`，均支持 MP3/WAV。本轮只处理公开 API 单人文本合成；未接声音克隆、长文任务和产品私有接口。

其中 Polly 需要 boto3，讯飞需要 websocket-client，其他客户端使用标准库。最新版 boto3 已不支持 Python 3.9，因此项目采用已核查 Requires-Python 的固定兼容版本，在 `.venv` 中安装，不修改全局 Python：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/alltts/requirements-optional.txt
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s test -v
```

已用 Python 3.9.13 完成安装和离线验证。依赖为 boto3/botocore 1.38.46、websocket-client 1.8.0，以及固定的传递依赖；升级时重新检查兼容性。

| provider | 环境变量 | 说明 |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | 官方 api.openai.com；默认 gpt-4o-mini-tts |
| `fish` | `FISH_API_KEY` | api.fish.audio；默认 s2.1-pro，voice 是实际 reference_id |
| `xfyun` | `XFYUN_APP_ID`、`XFYUN_API_KEY`、`XFYUN_API_SECRET` | 在线语音合成（流式版）产品凭据，控制台需开通 vcn |
| `google` | `GOOGLE_ACCESS_TOKEN`，可选 `GOOGLE_QUOTA_PROJECT` | Cloud TTS OAuth 访问令牌，具有 cloud-platform 权限；不是 Gemini Key。令牌过期需在本机更新，不自动登录/刷新 |
| `polly` | `AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`AWS_REGION`，可选 `AWS_SESSION_TOKEN` | SDK SigV4；显式环境凭据，不读共享凭据文件；需 Polly IAM 权限 |
| `baidu` | `BAIDU_API_KEY`、`BAIDU_SECRET_KEY` | 自动交换短期 access_token，保留在内存；不是直接传永久 token |
| `cartesia` | `CARTESIA_API_KEY` | 官方 Bearer 鉴权，固定 Cartesia-Version=2026-08-14，默认 sonic-3.6 |

音色查询：

```bash
.venv/bin/python skills/alltts/scripts/alltts.py voices --provider openai
.venv/bin/python skills/alltts/scripts/alltts.py voices --provider baidu
.venv/bin/python skills/alltts/scripts/alltts.py voices --provider xfyun
.venv/bin/python skills/alltts/scripts/alltts.py voices --provider fish --live
.venv/bin/python skills/alltts/scripts/alltts.py voices --provider google --live
.venv/bin/python skills/alltts/scripts/alltts.py voices --provider polly --live
.venv/bin/python skills/alltts/scripts/alltts.py voices --provider cartesia --live
```

OpenAI 记录13个预置音色和适配模型，未猜测性别/特质。百度记录短文本API参数表明确列出的44个候选，未声称穷尽全部音库。讯飞公开快照包含7个在线文档候选、64个超拟人音色、17个长文本音色；当前生成器仅实现在线 `/v2/tts`，其他两类查询返回其专属接口，生成时会拒绝混用。Fish 查询工作空间自有模型（`self=true`），保留描述和样本；不是全部社区音库。Google/Polly/Azure支持无密钥的官方公开快照查询，也保留 `--live` 账号/区域查询；Polly快照保留 `supported_engines` 并校验生成引擎。Cartesia保留账号可见目录和试听地址。分页重复、缺失或窗口受限会报错，不返回假装完整的目录。

音色与接口版本通过 `api_profiles` 关联 `api-profiles.json`，CLI直接返回相关接口配置。`voices --model MODEL` 筛选模型（Polly为engine），`voices --api-profile PROFILE` 筛选协议，`--runnable-only` 限定当前客户端实现范围。百炼目录扩展至Qwen实时、CosyVoice、Qwen-Audio及官方基础音色Excel；生成仍仅接上述48个qwen3-tts-flash音色。MiniMax新增61个本地历史候选，标记 `source_kind=local_historical`、`runnable=false`；当前模型与接口未核实。完整统计、Excel核对及缺口见 [voice-catalog-maintenance.md](voice-catalog-maintenance.md)。

生成示例：

```bash
.venv/bin/python skills/alltts/scripts/alltts.py generate --provider openai \
  --voice marin --style '自然清晰的普通话讲解' --text '你好，这是一段中文试听。' --output out/openai.mp3

# 先查询自己的音色，将返回的 _id 写入 FISH_VOICE_ID。
.venv/bin/python skills/alltts/scripts/alltts.py generate --provider fish \
  --voice "$FISH_VOICE_ID" --text '你好，这是一段中文试听。' --output out/fish.mp3

.venv/bin/python skills/alltts/scripts/alltts.py generate --provider xfyun \
  --voice x4_xiaoyan --xfyun-speed 50 --format wav --text '你好，这是一段中文试听。' --output out/xfyun.wav

# 从 Cloud TTS 目录确认音色及语言代码。
.venv/bin/python skills/alltts/scripts/alltts.py generate --provider google \
  --voice cmn-CN-Wavenet-A --language cmn-CN --format wav --text '你好，这是一段中文试听。' --output out/google.wav

# voice/engine 必须在所选 AWS 区域匹配，--model 在这里表示 engine。
.venv/bin/python skills/alltts/scripts/alltts.py generate --provider polly \
  --voice Zhiyu --model standard --format wav --text '你好，这是一段中文试听。' --output out/polly.wav

.venv/bin/python skills/alltts/scripts/alltts.py generate --provider baidu \
  --voice 0 --baidu-speed 5 --text '你好，这是一段中文试听。' --output out/baidu.mp3

# 将实时目录中的实际ID写入 CARTESIA_VOICE_ID。
.venv/bin/python skills/alltts/scripts/alltts.py generate --provider cartesia \
  --voice "$CARTESIA_VOICE_ID" --language zh --format wav --text '你好，这是一段中文试听。' --output out/cartesia.wav
```

参数与边界：

- OpenAI：4096字符；`--speed` 0.25–4；`--style` 映射 instructions，仅 gpt-4o-mini-tts 系列。tts-1/tts-1-hd 支持9个已核查音色；13个完整预置音色用于 mini TTS。自定义声音未接；官方说明音色优化英语，中文效果需试听。公开交付时告知听众语音由 AI 生成。
- Fish：HTTP音频流完整收集后保存；voice 是 reference_id。支持官方已核查的模型名，不自动回退；此客户端不注入风格标签、不映射 speed，不实现多人对话/克隆。
- 讯飞：少于8000 UTF-8字节；HMAC-SHA256 WebSocket握手，收到 `status=2` 才保存；支持成功空 data 帧，提前断连/超时/业务错误不保存部分音频。原生语速 `--xfyun-speed` 0–100；MP3 使用 lame，WAV 由 raw 16kHz/16bit/单声道PCM封装。控制台密钥与开通音色需匹配。
- Google：最多5000 UTF-8字节；普通音色 `--speed` 0.25–2；默认速度时不发送 speakingRate，Chirp音色不允许非默认 speed。LINEAR16 响应已经是 WAV，不重复封装。不接 Gemini-TTS 特殊模型/提示词/长文异步接口。
- Polly：最多3000纯文本计费字符；`--model` 为 standard/neural/long-form/generative；不映射 style/speed。MP3为24kHz；WAV将16kHz/16bit/单声道PCM正确封装。SDK关闭自动重试，读取后关闭音频流和客户端；音色/engine/区域可用性以真实账号调用为准。
- 百度：少于1024 GBK字节（按官方产品限制计算，传输仍是UTF-8）；不支持GBK无法表示的字符。文本做两次URL编码以保留 `+`、`&`、`%` 等符号；先检查音频 Content-Type，JSON错误不会保存为音频。`--baidu-speed` 为0–15。仅短文本基础接口，未接长文、情感及复刻。
- Cartesia：固定2026-08-14协议，voice 为字符串ID；`--speed` 0.6–1.5映射 generation_config，`--language` 传语言代码；MP3 44.1kHz/128kbps，WAV 44.1kHz/16bit。未把旧版的 voice.mode/X-API-Key 字段混入新版请求；自由文本style未映射。

本轮7家均已完成离线协议验证，当前运行环境未配置凭据，因此全部**未云端实测**。配置凭据后须各生成短样音、完整解码并试听，才能确认账号权限和音质。

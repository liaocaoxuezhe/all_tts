# ALLTTS · 为中文创作者找到合适的声音

[![Tests](https://github.com/liaocaoxuezhe/all_tts/actions/workflows/ci.yml/badge.svg)](https://github.com/liaocaoxuezhe/all_tts/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**查音色 → 选候选 → 同稿试听 → 生成旁白。** ALLTTS 是一个面向中文短视频、知识讲解、播客和口播的轻量 TTS CLI，也是一套可供 AI 编程助手使用的 Agent Skill。

不同厂商的音色 ID、鉴权、模型、音频格式和参数各不相同。ALLTTS 把这些接入差异收进一套命令，保留厂商原生能力和限制，让你把时间用在挑选声音与创作上。

## 为什么用 ALLTTS

- **先挑声音，再写接入代码。** 本地官方目录快照支持关键词搜索；6 类普通话场景提供带来源的试听候选。
- **用同一段文稿比较不同厂商。** 通过统一 `generate` 命令切换 provider、精确音色 ID 和输出文件，不必反复改写鉴权与解码逻辑。
- **适合人用，也适合 Agent 用。** CLI 输出 JSON，Skill 说明查询、选型、试听、生成和验收流程，可融入你自己的内容工作流。
- **上手轻。** Python 3.9+；大多数厂商只需标准库，AWS Polly 和讯飞才需要可选依赖；不下载模型权重。
- **输出可追溯。** 音频旁附 JSON 元数据，记录厂商、模型、音色、格式和文稿字数，不保存完整文稿或密钥。

> 当前版本实现 **14 家云服务及本机系统语音**。云端协议已通过离线测试，尚未逐家完成真实账号合成与音质验收。macOS 系统语音已真实生成并解码；Windows/Linux 待对应系统实测。音色推荐是有来源的候选，不是实测质量排行榜。

## 3 分钟开始

### 1. 获取项目

```bash
git clone https://github.com/liaocaoxuezhe/all_tts.git
cd all_tts
python3 --version  # 需要 Python 3.9 或更新版本
```

查询本地目录和场景推荐，无需 API Key，也无需安装 pip 包：

```bash
python3 skills/alltts/scripts/alltts.py recommend --scene knowledge
python3 skills/alltts/scripts/alltts.py voices --provider minimax --query 电台 --limit 5
```

可选场景：`knowledge` 知识讲解、`short-video` 短视频、`news` 新闻、`story` 故事、`warm` 温柔陪伴、`ad` 广告。当前精选推荐覆盖 MiniMax、火山和 Gemini；其他厂商请先查询目录再试听。

### 2. 配置你要用的厂商

```bash
cp .env.example .env
chmod 600 .env
# 在本机编辑 .env，只填要使用的厂商；不要修改 .env.example 中的空占位符
# .env 内容需要是可信的 shell 赋值语句，按模板用单引号包裹值
set -a
source .env
set +a
```

CLI **不会自动加载 `.env`**。以上操作需在运行 CLI 的同一个终端执行；Agent 宿主也需得到相应环境变量。`.env` 已被 Git 忽略。

完整变量清单见 [.env.example](.env.example)，各厂商区域、权限和格式要求见 [配置与调用](skills/alltts/references/usage.md)。只查公开目录不需要密钥；生成云音频会使用你的账号并可能计费。

### 3. 生成一段试听

```bash
python3 skills/alltts/scripts/alltts.py generate --provider minimax \
  --voice 'Chinese (Mandarin)_Radio_Host' \
  --text '今天，我们来解释一个容易被误解的概念。' \
  --output out/minimax-demo.mp3
```

结果是 `out/minimax-demo.mp3` 与 `out/minimax-demo.mp3.json`。同名音频或元数据存在时会拒绝覆盖。正式文稿建议用 `--text-file 文稿.txt` 读取 UTF-8 文件。

不想配置云服务，可先尝试本机语音：

```bash
python3 skills/alltts/scripts/alltts.py voices --provider system --live
# macOS 示例：把 Tingting 替换成上一条命令实际返回的音色 ID
python3 skills/alltts/scripts/alltts.py generate --provider system \
  --voice Tingting --format aiff --text '你好，这是本机系统语音。' \
  --output out/system-demo.aiff
```

macOS 使用 `say` 输出 AIFF；Windows 使用 System.Speech 输出 WAV；Linux 需要另行安装 `espeak-ng`，输出 WAV。音色以本机枚举为准。

## 支持哪些服务

| 服务 | provider | 本客户端输出 | 音色来源 / 特点 |
|---|---|---|---|
| MiniMax | `minimax` | MP3 | 327 个系统音色快照；账号音色实时查询；中国/国际区域 |
| 火山 / 豆包 | `volcengine` | MP3 | 578 条跨产品表记录，294 条属于当前可生成的 2.0 表 |
| Gemini Developer API | `gemini` | WAV | 30 个预置音色；扩展库分页；自然语言风格 |
| 阿里百炼 | `aliyun` | WAV | 48 个 qwen3-tts-flash 系统音色；北京/新加坡 |
| 腾讯云 | `tencent` | MP3 / WAV | 67 条官方目录记录；TC3 签名；短文本 |
| Azure Speech | `azure` | MP3 / WAV | 区域音色实时查询；SSML、语速、已校验的风格 |
| ElevenLabs | `elevenlabs` | MP3 | 当前账号目录分页；保留描述和试听 URL |
| OpenAI Speech | `openai` | MP3 / WAV | 13 个预置音色；按模型校验；instructions |
| Fish Audio | `fish` | MP3 / WAV | 工作空间自有模型分页；reference_id |
| 科大讯飞 | `xfyun` | MP3 / WAV | WebSocket；官方 vcn 候选，权限以控制台为准 |
| Google Cloud TTS | `google` | MP3 / WAV | OAuth；实时官方音色目录；与 Gemini API 分开配置 |
| AWS Polly | `polly` | MP3 / WAV | SDK SigV4；区域音色 / engine；可选依赖 |
| 百度智能云 | `baidu` | MP3 / WAV | 44 个参数表音库候选；短文本与令牌交换 |
| Cartesia | `cartesia` | MP3 / WAV | 账号音色分页；Sonic 3 系列 |
| 本机语音 | `system` | AIFF / WAV | 无云端 Key；枚举本机已安装音色 |

目录快照有日期和官方来源，记录数不等于唯一可用音色数。实际权限、模型兼容性及价格以厂商为准。详细接入状态见 [providers.md](skills/alltts/references/providers.md)。

### 同稿比较多个候选

准备 `文稿.txt`，然后为每个候选指定不同文件名：

```bash
python3 skills/alltts/scripts/alltts.py generate --provider minimax \
  --voice 'Chinese (Mandarin)_Radio_Host' --text-file 文稿.txt --output out/minimax.mp3

python3 skills/alltts/scripts/alltts.py generate --provider gemini \
  --voice Charon --format wav --style '清晰自然的普通话知识讲解，语速适中。' \
  --text-file 文稿.txt --output out/gemini.wav
```

需分别配置两家凭据。抽听开头、中间、结尾，尤其关注多音字、数字和英文缩写；文件头检查通过不代表音质合格。跨厂商语速参数并不等价，请按 [usage.md](skills/alltts/references/usage.md) 使用。

## 作为 Agent Skill 使用

技能入口是 [skills/alltts/SKILL.md](skills/alltts/SKILL.md)。仓库中的 `.agents/skills/alltts` 相对符号链接指向此目录，支持项目技能发现的工具可直接使用；若尚未出现，刷新或新开项目聊天，也可以直接提供入口路径。

例如：

> 使用 ALLTTS，为这段中文知识短视频挑三个有来源的候选。先查询目录，使用我已配置的厂商，同稿各生成一段试听，给我音频和元数据。

技能只使用用户在执行环境中配置的凭据，不扫描其他项目的密钥。不同 Agent 的技能发现与环境变量注入方式可能不同。

## 安全与功能边界

- 凭据仅通过环境变量使用；仓库只有空 `.env.example`。API 请求发送到对应厂商，文稿会交给该厂商处理；使用云服务前请了解其数据政策。
- HTTP 只允许 HTTPS，并拒绝自动重定向；讯飞禁用 WebSocket 重定向；Polly 忽略 SDK 自定义端点配置。
- 错误输出不打印原始 HTTP/SDK 响应、签名 URL 或 traceback；已配置密钥在 JSON 输出与元数据中脱敏。
- 不自动重试、不自动切换厂商，避免超时后重复计费。超时不代表服务端没有执行。
- 输出使用临时文件与硬链接发布，拒绝覆盖；元数据发布失败会清理本次音频。输出目录需支持硬链接，例如常见本地文件系统。
- 当前只做单人文本配音。暂不支持自动长文分段/拼接、声音克隆、字幕、多人对白、模型本地部署或私有产品接口。
- 音频检查目前仅为容器头检查；可进一步使用 ffprobe/ffmpeg 完整解码，再试听。实时目录可能包含账号私有音色信息，分享前请检查。

更多安全说明与私密漏洞报告方式见 [SECURITY.md](SECURITY.md)。

## 开发与验证

可选依赖已固定为 Python 3.9 兼容版本；新 clone 不包含开发者本机虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r skills/alltts/requirements-optional.txt
python -m pip check
python -m unittest discover -s test -v
```

测试使用模拟 HTTP/WebSocket、官方签名向量和 SDK Stubber，不需要真实 Key，也不会调用计费接口。CI 覆盖 Python 3.9 与 3.13，并扫描 Git 历史中的疑似凭据。测试文件统一位于 `test/`。

目录布局：

```text
skills/alltts/          Agent Skill、CLI、官方音色快照和使用参考
.agents/skills/alltts   指向技能目录的相对符号链接
test/                  离线协议与安全回归测试
.env.example           空凭据配置模板
SECURITY.md            安全边界与私密报告方式
CONTRIBUTING.md        扩展厂商与贡献说明
```

验证范围见 [test/validation.md](test/validation.md)，发布前审查见 [CODE_REVIEW.md](CODE_REVIEW.md)。贡献方法见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可与致谢

本项目原创代码及文档采用 [MIT License](LICENSE)。音色名称、目录描述和 API 规范来自各厂商公开资料，来源与核查日期保留在快照和参考文档中；相关商标、服务和音频使用权仍遵循厂商条款。仓库不分发第三方完整网页/PDF、模型权重、账号凭据或私人生成音频。

---
name: alltts
description: 为中文短视频、口播和知识内容选择 TTS 音色，按官方目录与可追溯社区经验推荐试听候选，并使用用户配置的火山、MiniMax、Gemini、百炼、腾讯云、Azure Speech、ElevenLabs API 或系统语音生成音频。
---

# ALLTTS

在用户的内容场景、语言、已配置厂商和声音偏好之间选出可调用音色，先试听，再生成。工作目录不必是技能目录；下文 `<skill>` 表示本文件所在目录，执行时替换成实际绝对路径。客户端支持 Python 3.9+；基础HTTP使用标准库，Polly/讯飞使用项目虚拟环境中的可选依赖。

## 选择与试听

1. 从用户文稿和要求确定语言、用途、声音气质、时长与预算。缺少的信息只问影响选型的部分；已有偏好直接沿用。用户只要求推荐时，不调用计费接口。
2. 查看 [providers.md](references/providers.md) 的接入状态。P0和P1列出的全部公开API厂商已有单人文本客户端；P2受限渠道/本地模型仍暂缓。云端未实测时不能说已经接通。系统语音由操作系统决定，无需 API Key。
3. 按需查目录，避免一次把所有音色加载进上下文：
   ```bash
   python3 <skill>/scripts/alltts.py voices --provider minimax --query 电台 --limit 8
   python3 <skill>/scripts/alltts.py voices --provider volcengine --query 解说 --limit 8
   python3 <skill>/scripts/alltts.py recommend --scene knowledge
   ```
   场景值：`knowledge` 知识、`short-video` 短视频、`news` 新闻、`story` 故事、`warm` 温柔陪伴、`ad` 广告。用 `voices --model MODEL`、`--api-profile PROFILE` 筛选版本，用 `--runnable-only` 限定当前客户端支持的协议。查询返回 `api_profiles` 中的地址、版本及参数位置；详情见 [目录维护记录](references/voice-catalog-maintenance.md)。精选推荐当前面向普通话。其他语言按目录和实际试听选择，不沿用普通话排名。
4. 推荐通常给出三个候选，包含厂商、精确 ID、官方名称/描述、推荐理由、证据类型和限制。参考 [community.md](references/community.md)。官方名称不等于实测声音特征；无原帖证据不能写“社区公认”。不能从产品内显示名猜 API ID。
5. 用户要求试听时，以同一段约 60–120 字文稿、相同内容生成候选样音，使用独立文件名，展示音频供选择。用户已指定音色并要求完整生成时直接生成，不重复要求确认。未选音色且没有授权自动选型时，先交付试听，不擅自生成整篇。

## 配置与生成

读取 [usage.md](references/usage.md) 获取密钥变量、系统差异、格式和命令。密钥由用户在本机设置；不索要在聊天中粘贴密钥，不读取其他项目的凭证。环境变量是否存在可检查，但不输出值。

```bash
python3 <skill>/scripts/alltts.py generate --provider minimax \
  --voice 'Chinese (Mandarin)_Radio_Host' --text-file /绝对路径/文稿.txt \
  --output /绝对路径/旁白.mp3
```

- MiniMax、火山、ElevenLabs 输出 MP3；Gemini、百炼 Qwen-TTS 输出 WAV；腾讯云和 Azure 支持 MP3/WAV；macOS 系统输出 AIFF，Windows/Linux 输出 WAV。不要只修改扩展名来转换格式。
- `--style` 映射到 Gemini 的 speech_metadata 或 Azure 的官方 StyleList（合成前核查区域音色支持）；腾讯用 `--tencent-speed` 原生刻度，默认0。语速参数不能跨厂商照搬。其余7家配置、语速及音色查询规则见 usage.md；Polly/讯飞用 `.venv/bin/python` 执行。当前范围是单人文本配音，不包含声音克隆、字幕、多人对白或异步长文。
- `voices --live --provider minimax` 查询账号音色及官方描述；Gemini 同命令遍历扩展库分页，Azure 查询区域目录，ElevenLabs 遍历账号分页并保留描述/标签/试听URL。系统音色实时枚举。百炼只接 qwen3-tts-flash 非实时系统音色；百炼/腾讯/火山采用公开目录快照，账号授权仍以控制台为准。
- 2026-10-11 扩展讯飞、阿里、腾讯、Azure、Google、Polly 并刷新 MiniMax 官方表；原火山/Gemini仍保留2026-10-10快照。MiniMax 本地2024历史表的61个额外ID无已核实接口，禁止当作当前系统音色调用；历史描述不冒充官方描述。火山目录保留多个产品表，生成器仅允许第一表的 2.0 TTS 音色，其他表的资源映射仍待核实。遇到下线、权限或模型变化时打开记录的官方来源更新资料，不盲目重试。
- 长文按自然段分段，先列出分段与输出计划。当前 CLI 一次生成一个文件；拼接须使用音频工具重新封装，不能拼接 WAV 文件字节。不要承诺精确时长或跨段音色绝对一致。
- 网络超时可能已经计费；客户端不自动重试，也不自动换厂商。先确认错误与输出状态，再决定下一次请求。

## 交付

客户端只完成基础容器头检查。若有 ffprobe/ffmpeg，再检查时长、声道、采样率和可解码性；至少抽听开头、中间、结尾及多音字/数字/英文缩写。仅检查文件存在不足以声称配音质量合格。

交付音频绝对路径链接及旁边的 `.json` 元数据，说明厂商、模型、音色、格式和实际验证范围。用 `![试听](/绝对路径/样音.mp3)` 展示可播放音频。没有用户密钥时交付配置方法，明确云端未实测；不要把模拟响应测试当成真实合成。

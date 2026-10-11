# AI 视频配音 TTS 音色核实表（2026-10-10）

核实规则：只有在官方文档里看到的 ID 才标「已核实」；第三方页面上看到的标「未核实」；完全找不到的写「未找到」。

| 服务商 | 音色 | 音色 ID | 适合场景 | API/文档链接 | 备注 |
|---|---|---|---|---|---|
| 剪映/CapCut 文本朗读 | 深夜诉说 | 未找到 | 情感/深夜电台类短视频旁白 | 无官方公开 TTS API | 剪映没有公开的文本朗读 API。火山官方文档里找不到剪映音色名和 voice_type 的对应关系，不要自己猜 |
| 剪映/CapCut 文本朗读 | 温柔女声 | 未找到 | 温柔种草、生活 vlog | 同上 | 可以用火山 2.0「温柔淑女」zh_female_wenroushunv_uranus_bigtts 代替（未核实，见下方火山行） |
| 剪映/CapCut 文本朗读 | 童声 | 未找到 | 儿童、绘本、萌宠 | 同上 | 可以用火山「儿童绘本 2.0」zh_female_xiaoxue_uranus_bigtts 代替（未核实，第三方列表） |
| 剪映/CapCut 文本朗读 | 老年男声 | 未找到 | 故事、怀旧、搞笑 | 同上 | — |
| 剪映/CapCut 文本朗读 | 解说小帅 | 未找到 | 影视解说 | 同上 | 火山 2.0 有「解说小明 2.0」zh_male_jieshuoxiaoming_uranus_bigtts（未核实，第三方列表），不一定是同一个音色 |
| 剪映/CapCut 文本朗读 | 磁性男声 | 未找到 | 影视解说、广告 | 同上 | 可以用火山 2.0「磁性解说男声」zh_male_cixingjieshuonan_uranus_bigtts 代替（未核实） |
| MiniMax Speech | 电台男主播 | `Chinese (Mandarin)_Radio_Host` | 播客、电台、知识类旁白 | https://platform.minimaxi.com/docs/faq/system-voice-id | 已核实 |
| MiniMax Speech | 沉稳高管 | `Chinese (Mandarin)_Reliable_Executive` | 商业、财经、企业宣传 | 同上 | 已核实 |
| MiniMax Speech | 新闻女声 | `Chinese (Mandarin)_News_Anchor` | 新闻播报、资讯 | 同上 | 已核实 |
| MiniMax Speech | 播报男声 | `Chinese (Mandarin)_Male_Announcer` | 播报、通知、产品介绍 | 同上 | 已核实 |
| MiniMax Speech | 温润男声 | `Chinese (Mandarin)_Gentleman` | 情感、品牌故事 | 同上 | 已核实 |
| MiniMax Speech | 声音复刻 | 复刻后返回自定义 voice_id | 用自己或品牌的声音做配音 | https://platform.minimaxi.com/docs/api-reference/voice-cloning-clone | 已核实：先 POST /v1/files/upload 上传音频，再 POST /v1/voice_clone。复刻音色 7 天内没有正式调用会被删除，并且需要先完成实名认证 |
| 火山引擎 豆包语音合成 2.0 | Vivi 2.0（官方示例默认女声） | `zh_female_vv_uranus_bigtts` | 通用女声旁白 | https://docs.volcengine.com/docs/DoubaoVoice/unidirectional-streaming-text-to-speech-http?lang=zh | 已核实（官方接口示例里出现） |
| 火山引擎 豆包语音合成 2.0 | 磁性解说男声 | `zh_male_cixingjieshuonan_uranus_bigtts` | 影视解说、沉稳旁白 | 官方音色列表 https://www.volcengine.com/docs/6561/1257544 | 未核实：官方列表页是 JS 渲染，抓不到内容，这个 ID 只在第三方 LinkAI 列表里看到 |
| 火山引擎 豆包语音合成 2.0 | 云舟 2.0（通用男声） | `zh_male_m191_uranus_bigtts` | 通用男声旁白 | 同上 | 未核实（只在第三方列表里看到） |
| 火山引擎 豆包语音合成 2.0 | 高冷沉稳 | `zh_male_gaolengchenwen_uranus_bigtts` | 沉稳男声 | 同上 | 未核实（只在第三方列表里看到） |
| 火山引擎 豆包语音合成 2.0 | 温柔淑女 2.0 | `zh_female_wenroushunv_uranus_bigtts` | 温柔女声 | 同上 | 未核实（只在第三方列表里看到） |
| 火山引擎 豆包语音合成 2.0 | 声音复刻 2.0 | 复刻后得到的 speaker ID | 定制音色 | https://docs.volcengine.com/docs/6561/1305191?lang=zh | 已核实：合成时 X-Api-Resource-Id 填 seed-icl-2.0，训练时 model_type=4 或 5 |
| Microsoft Azure | 云希 Yunxi | `zh-CN-YunxiNeural` | 年轻男声旁白、解说（支持 narration-relaxed 等多种风格） | https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts | 已核实 |
| Microsoft Azure | 云扬 Yunyang | `zh-CN-YunyangNeural` | 新闻、专业播报 | 同上 | 已核实 |
| Microsoft Azure | 晓晓 Xiaoxiao | `zh-CN-XiaoxiaoNeural` | 通用女声、多情感 | 同上 | 已核实。edge-tts（https://github.com/rany2/edge-tts）是非官方库，调用的是 Edge 浏览器的朗读接口，没有 SLA，商用有风险 |
| ElevenLabs | Adam | 未找到 | 美式男声旁白 | https://elevenlabs.io/docs/api-reference/text-to-speech/convert | 官方文档正文里没有给出 Adam 的 voice_id，可以调 GET /v1/voices 查。另外官方提示所有 Default 音色会在 2026-12-31 下线 |
| ElevenLabs | Daniel | 未找到 | 英式男声、新闻 | 同上 | 同上 |
| Gemini TTS | 30 个预置音色 | Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat | 旁白（Charon、Rasalgethi 偏信息播报）、播客双人对话 | https://ai.google.dev/gemini-api/docs/speech-generation | 已核实。模型：gemini-3.8-flash-tts / gemini-3.8-flash-lite-tts。另有扩展音色库 GET /v1beta/voices，并支持 Voice design 和 Voice replication（声音复刻） |
| Fish Audio | 任意库内或自建音色 | 用 `reference_id` 指定（音色模型 ID） | 多语种配音、克隆、多人对话 | https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech | 已核实：模型放在 header `model` 里，可选 s1 / s2-pro / s2.1-pro（默认）/ s2.1-pro-free / drama-3-preview。官方文档没有列出具体的库内音色 ID |

## 各服务商接口与文档地址
- MiniMax：POST https://api.minimax.cn/v1/t2a_v2；模型 speech-2.8-hd / speech-2.8-turbo / speech-2.6-hd / speech-2.6-turbo / speech-02-* / speech-01-*；系统音色列表 https://platform.minimaxi.com/docs/faq/system-voice-id；复刻接口 POST /v1/voice_clone
- 火山豆包 2.0：POST https://openspeech.bytedance.com/api/v3/tts/unidirectional（另有 WebSocket：wss://openspeech.bytedance.com/api/v3/tts/bidirection），X-Api-Resource-Id 填 seed-tts-2.0 或 seed-icl-2.0；音色列表 https://www.volcengine.com/docs/6561/1257544；也可以调 ListSpeakers 接口查（Action=ListSpeakers&Version=2025-05-20）
- Azure：POST https://{region}.tts.speech.microsoft.com/cognitiveservices/v1（请求体为 SSML），音色列表接口 /tts/cognitiveservices/voices/list
- ElevenLabs：POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}；模型 eleven_v4、eleven_v4_turbo、eleven_v3、eleven_multilingual_v2（默认）、eleven_flash_v2_5、eleven_turbo_v2_5
- Gemini：POST https://generativelanguage.googleapis.com/v1beta/interactions
- Fish Audio：POST https://api.fish.audio/v1/tts

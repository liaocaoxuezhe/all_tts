# 厂商优先级与接入研究

原P0/四家P1核查日期：2026-10-10；剩余7家更新：2026-10-11。优先级依据用户确认的中文短视频、口播和知识内容用途，综合中文适配、公开 API、目录可获取性与接入复杂度；不是音质实测排名，也不宣称穷尽全球供应商。P0/P1表内全部公开API厂商已交付单人文本配音客户端，P2继续暂缓。

## P0：当前实现

| 厂商 | 接入方式与鉴权 | 音色与说明覆盖 | 客户端状态 |
|---|---|---|---|
| 火山/豆包语音 | POST `https://openspeech.bytedance.com/api/v3/tts/unidirectional`；X-Api-Key、X-Api-Resource-Id=`seed-tts-2.0`、X-Api-Request-Id；响应按 JSON 音频块处理 | 官方页4表共578条记录，保留场景、语种、能力、情感与产品表；294条来自2.0表。记录可跨表重复，不是578个唯一可合成音色 | MP3合成实现，公开目录实现；账号授权以控制台为准，无真实云调用 |
| MiniMax | POST `https://api.minimax.cn/v1/t2a_v2`；Bearer Key；国际站 `https://api.minimax.io` | 系统音色文档327条全表；POST `/v1/get_voice` 查询账号音色和 description。静态名称不冒充详细描述 | MP3合成与账号查询实现，无真实云调用 |
| Gemini | POST `https://generativelanguage.googleapis.com/v1beta/interactions`；x-goog-api-key；语音模型与风格注解 | 30个预置音色及中文特征释义；GET `/v1beta/voices` 分页查询扩展/自定义库和 description | 单人WAV合成与完整分页实现，无真实云调用 |
| 系统语音 | 本机语音引擎，不用云密钥 | 动态枚举，区分macOS/Windows/Linux | macOS真实生成验证；Windows/Linux实现但尚无对应系统实测 |

官方来源：

- 火山：[HTTP接口](https://docs.volcengine.com/docs/DoubaoVoice/unidirectional-streaming-text-to-speech-http?lang=zh)、[音色目录](https://docs.volcengine.com/docs/DoubaoVoice/Tonelist-1?lang=zh)。新版接口是 X-Api-Key，不应照抄旧版 AppId/Access Token 教程。TTS、S2S、复刻资源各有边界。
- MiniMax：[HTTP接口](https://platform.minimax.cn/docs/api-reference/speech-t2a-http)、[系统音色](https://platform.minimax.cn/docs/faq/system-voice-id)、[账号音色查询](https://platform.minimax.cn/docs/api-reference/voice-management-get)。同步响应默认音频是 hex，不是 base64；先检查 base_resp 再解码。
- Gemini：[语音生成与音色目录](https://ai.google.dev/gemini-api/docs/speech-generation)、[Interactions参考](https://ai.google.dev/api/interactions-api)。当前官方指南采用3.8 TTS与Interactions；不要套用历史2.5的generateContent请求格式。非流式WAV与流式裸PCM不同。
- 系统：[Apple音色枚举](https://developer.apple.com/documentation/avfaudio/avspeechsynthesisvoice/speechvoices())、[Windows音色枚举](https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.getinstalledvoices)、[espeak-ng官方语音说明](https://github.com/espeak-ng/espeak-ng/blob/master/docs/voices.md)。macOS CLI 细节以本机 `man say` 为准。

## P1：公开 API 扩展

| 厂商/产品 | API与鉴权 | 全音色和官方说明取得方式 | 优先依据/实现注意 |
|---|---|---|---|
| 阿里百炼 Qwen-TTS / Qwen-Audio-TTS / CosyVoice | DashScope REST/WebSocket；Bearer API Key；地区/工作空间和模型决定地址 | [Qwen-TTS API](https://help.aliyun.com/zh/model-studio/qwen-tts-api)、[Qwen-Audio-TTS音色表](https://help.aliyun.cn/zh/model-studio/qwen-audio-tts-voice-list)。表中有音色ID、特质、用途、适配模型；克隆/设计需账号查询 | 中文优先候选。不同模型音色不能混用；不要把开源Qwen与云API混为一项；地区密钥和地址配套 |
| 腾讯云 TTS | `tts.tencentcloudapi.com`；TextToVoice，Version=2019-08-23；SecretId/SecretKey，TC3签名 | [接口与音色目录入口](https://cloud.tencent.com/document/product/1073/37995)，VoiceType是整数，情感/采样率依音色；克隆另有FastVoiceType | 可靠中文API；基础接口限制较短，长文需对应接口/分段；不是“微信读书API” |
| Azure Speech | POST `https://{region}.tts.speech.microsoft.com/cognitiveservices/v1`；Speech Key+Region或令牌；SSML | GET `https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list`，返回名称、性别、locale、style等；[官方REST参考](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech)、[语言音色表](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts) | 多语种和SSML控制；全表用区域API实时同步，音色style不能泛化到所有音色 |
| OpenAI Speech | POST `https://api.openai.com/v1/audio/speech`；Bearer API Key；model/input/voice | [官方音色与模型说明](https://developers.openai.com/api/docs/guides/text-to-speech)。预置名按模型支持核查，自定义声音另有权限 | 易接入，适合可控旁白；官方推荐与社区推荐分开，不能自行猜声音性别 |
| ElevenLabs | POST `/v1/text-to-speech/{voice_id}`；xi-api-key | [GET `/v2/voices`分页/搜索](https://elevenlabs.io/docs/api-reference/voices/search)，获取description/labels/preview；[合成接口](https://elevenlabs.io/docs/api-reference/text-to-speech/convert) | 多语种、表达控制；音色库包含共享/私有/账号加入的音色，必须查询可用ID；不能用Adam等显示名推断ID |
| Fish Audio | POST `https://api.fish.audio/v1/tts`；Bearer Key；模型在header，voice用reference_id | [官方合成参考](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech)，音色来自官方模型库/账号模型；不是固定小规模预置表 | 中文/角色对白扩展；不预置来源不明的真人克隆ID，当前未同步其全库 |
| 科大讯飞 | WebSocket流式TTS，AppId/APIKey/APISecret，HMAC-SHA256握手鉴权 | [官方接口和发音人参数](https://www.xfyun.cn/doc/tts/online_tts/API.html)，vcn按服务开通范围选择 | 中文传统服务覆盖；旧普通HTTP入口不再对外开放，不用旧教程伪装新接入 |
| Google Cloud TTS | POST `https://texttospeech.googleapis.com/v1/text:synthesize`；Google Cloud鉴权与项目计费 | GET `/v1/voices`；[完整音色列表API](https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/voices/list) | 多语种/企业服务；Cloud TTS与Gemini Developer API是不同产品，权限/模型/声音名不可直接交换 |
| AWS Polly | POST `/v1/speech`；区域端点，IAM/SigV4；SynthesizeSpeech | [DescribeVoices](https://docs.aws.amazon.com/cli/latest/reference/polly/describe-voices.html)、[SynthesizeSpeech](https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html)，返回语言与SupportedEngines，需遍历NextToken | 企业多语种；engine/voice/region匹配，优先用官方SDK处理签名 |
| 百度智能云 TTS | REST/SDK；API Key+Secret Key获取access_token；不同新旧产品各有接口 | [官方TTS产品/API入口](https://ai.baidu.com/tech/speech/tts)，per音库ID必须按所开通产品核查；[复刻合成接口](https://ai.baidu.com/ai-doc/SPEECH/qmjiax60m)与普通TTS不能混用 | 中文传统音库；access_token不是永久Key，音频错误响应可能是JSON，先检查响应类型 |
| Cartesia | POST `https://api.cartesia.ai/tts/bytes`；X-API-Key和Cartesia-Version；voice.id | [官方Bytes API](https://docs.cartesia.ai/api-reference/tts/bytes)，音色按官方voices API及账号库查询 | 低延迟语音代理候选；中文内容本项目优先级低于前三项；核查模型、API版本与输出格式 |

本轮实现状态：

| provider | 已实现 | 边界/验证 |
|---|---|---|
| `aliyun` | qwen3-tts-flash 非流式 HTTP；北京/新加坡区域；下载完整 WAV；48 个官方系统音色 | 600 字符；未接 Qwen-Audio-TTS、CosyVoice、实时、克隆和工作空间专属端点；未云端实测 |
| `tencent` | TextToVoice；标准库 TC3-HMAC-SHA256；MP3/WAV；67 条官方音色快照 | 签名通过官方固定向量；中国站、16kHz；150 中文/500 ASCII 字符，混合文本保守按150；未接长文/复刻；未云端实测 |
| `azure` | 区域实时音色列表；SSML 合成、转义文稿、速率与校验后的风格；MP3/WAV | 公有云 Speech Key+Region；10 分钟上限，长文需分段；主权云/自定义音色未接；未云端实测 |
| `elevenlabs` | v2 账号音色完整分页，保留描述/标签/试听URL；v1 合成、MP3 | 默认 eleven_multilingual_v2；音色ID从账号查询；克隆、对话和模型专属控制未接；未云端实测 |

其余7家P1已实现，见下表。目录可查询性不代表账号已获得所有音色/模型权限。Azure/ElevenLabs 必须用用户配置密钥实时查询，不以静态名单声称覆盖全部库。

本轮音色来源：[Qwen-TTS 音色表](https://help.aliyun.com/zh/model-studio/qwen-tts-voice-list)、[腾讯音色表](https://cloud.tencent.com/document/product/1073/92668)、[腾讯 TextToVoice](https://cloud.tencent.com/document/api/1073/37995)、[腾讯 TC3 签名规范](https://cloud.tencent.com/document/api/306/57449)。原始目录 HTML 仅在本机 `test/` 保留，不随仓库分发；构建脚本为 `test/build_p1_catalogs.py`，使用方法见 CONTRIBUTING.md。

## P2：受限渠道与暂缓范围

| 渠道 | 调研结论 | 当前动作 |
|---|---|---|
| 微信同声传译小程序插件 | 腾讯官方[Face2FaceTranslator示例](https://github.com/Tencent/Face2FaceTranslator)记录插件语音合成；这是微信小程序运行环境中的能力，不能当通用服务器REST API。示例年代较早，当前权限/维护状态尚待插件官方页面确认 | 不接入；用户若指腾讯云则走P1腾讯云，微信读书私人接口不收录 |
| 剪映/CapCut创作工具配音 | 未验证可供用户自配Key的通用公开TTS API。部分火山官方音色带“剪映同款”标签，只对这些明确标记成立 | 用官方火山ID；不建立未经验证的显示名对应关系，不逆向产品私有接口 |
| Edge朗读/edge-tts | [edge-tts仓库](https://github.com/rany2/edge-tts)是社区客户端，不等同Azure正式API，也不等同离线Windows系统语音 | 不纳入P0；需要正式云接口时走Azure |
| B站及本地开源TTS | 用户明确暂不处理B站开源方案，只处理API请求；无指定开源产品时不能猜是IndexTTS、GPT-SoVITS或其他模型 | 暂缓，不搭建模型、不下载权重 |

## 扩展接入规范

添加P1供应商时，在 `scripts/alltts.py` 注册provider，添加独立的鉴权、列表查询、请求构造和音频解码分支；不要用“OpenAI兼容”假设所有供应商都可复用字段。复杂签名优先官方SDK，先检查Python3.9兼容性；本轮腾讯为保持零依赖按官方 TC3 规范实现，并通过官方固定签名向量验证。

新增目录字段：provider、id、name、language、official_description、model/resource/region、source、verified_at、account_scope、runnable。保留description缺失状态，场景推断放独立推荐文件。列表必须完成分页；请求失败时保留旧目录并标记刷新失败。

接入验收：放在当前项目 `test/` 的模拟测试覆盖真实协议的成功/业务错误/HTTP错误/空音频/超时；使用用户提供的该厂商密钥后再做小样真实生成并试听。未真实调用前标“实现未云端实测”，不标“已接通”。

## 2026-10-11：剩余7家已实现

| provider | 实现 | 目录与边界 |
|---|---|---|
| `openai` | /v1/audio/speech，Bearer，MP3/WAV，速度/instructions | 13预置音色，模型适配检查；自定义声音未接 |
| `fish` | /v1/tts，Bearer及model header，MP3/WAV | /model自有工作空间完整分页；不是全部社区音库 |
| `xfyun` | /v2/tts HMAC-SHA256 WebSocket，MP3/raw转WAV | 官方vcn示例，实际开通范围由控制台确认；不编造列表API |
| `google` | Cloud /v1/text:synthesize，OAuth，MP3/LINEAR16 WAV | /v1/voices官方目录；不等同Gemini Developer API；不接特殊Gemini-TTS模型 |
| `polly` | 官方boto3 SigV4，MP3/PCM转WAV，关闭自动重试 | DescribeVoices完整NextToken分页，区域/engine/voice需匹配 |
| `baidu` | OAuth token交换，text2audio双重编码，MP3/WAV | 参数表44个音库候选；小于1024 GBK字节；未接长文本及复刻 |
| `cartesia` | 2026-08-14 Bearer协议，Sonic 3系列，MP3/WAV | /voices游标完整分页，使用新版字符串voice ID |

全部通过离线协议测试，**未云端实测**。当前环境未配置7家凭据。Python3.9兼容的可选SDK固定在 requirements-optional.txt；需按 usage.md 自行创建虚拟环境并安装。调用和参数边界见 usage.md。

补充核查来源：[OpenAI Speech](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create)、[Fish合成](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech)、[Fish模型查询](https://docs.fish.audio/api-reference/endpoint/model/list-models)、[讯飞在线合成](https://www.xfyun.cn/doc/tts/online_tts/API.html)、[Google合成](https://docs.cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize)、[Polly合成](https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html)、[百度官方PDF（短文本API第232–234页）](https://bce.bdstatic.com/p3m/pdf/ai-cloud-share/online/SPEECH/SPEECH.pdf)、[Cartesia新版合成](https://docs.cartesia.ai/api-reference/tts/bytes)、[Cartesia目录](https://docs.cartesia.ai/api-reference/voices/list)。

# 音色目录与接口对应记录

本轮核查：2026-10-11。公开目录从原1108条扩展至5784条，覆盖11家静态目录；ElevenLabs、Fish、Cartesia继续通过账号API查询。记录以厂商、音色ID、产品/模型、接口为单位，跨产品或语言的同一个ID可能出现多次，不能将记录数当作唯一音色数。

## 当前覆盖

| 厂商 | 记录数 | 唯一ID | 本轮范围 |
|---|---:|---:|---|
| MiniMax | 388 | 388 | 327条官方系统音色；61条用户历史表额外ID |
| 火山 | 578 | 573 | 保留2026-10-10四产品表快照；294条2.0可由当前生成器调用 |
| Gemini | 30 | 30 | 保留预置目录；扩展及自定义库需账号API |
| 阿里百炼 | 1588 | 1538 | Qwen非实时/实时、CosyVoice各模型、Qwen-Audio各模型及官方基础音色Excel |
| 腾讯 | 151 | 60 | 实时60条、基础60条、长文本31条分别绑定接口 |
| Azure | 761 | 759 | 全球Text to speech voices表；区域/预览授权需实时核对 |
| Google Cloud | 2032 | 2032 | 官方支持语言完整表，保留语种、类别和音色系列 |
| AWS Polly | 111 | 109 | 多语言音色及四种引擎矩阵；精确ID用API枚举交叉验证 |
| OpenAI | 13 | 13 | 保留官方预置目录和模型适配记录 |
| 百度 | 44 | 44 | 保留短文本API参数表音库候选；不是全产品音库 |
| 科大讯飞 | 88 | 88 | 在线文档7个候选、超拟人公开表64条、长文本附录17条 |

阿里模型细分：`qwen3-tts-flash` 48、`qwen3-tts-flash-realtime` 48、`cosyvoice-v3-flash` 88、`cosyvoice-v3-plus` 2、`cosyvoice-v2` 106、`cosyvoice-v1` 20、`qwen-audio-3.1-tts-flash` 68、`qwen-audio-3.0-tts-plus` 599、`qwen-audio-3.0-tts-flash` 609。Qwen-Audio的基础音色来自官方Excel；不是根据命名规则批量编造ID。

## 版本与可调用性

`*-voices.json` 中每条记录的 `api_profiles` 关联 [api-profiles.json](api-profiles.json)，配置包含endpoint、api_version、voice_parameter、官方来源和必要的resource/action等字段。`model`保留音色支持的模型或产品族；没有独立模型参数的产品不能把它直接发送到请求中。

- 讯飞在线是 `wss://tts-api.xfyun.cn/v2/tts`，音色参数 `business.vcn`；超拟人是 `/v1/private/mcd9m97e6`，参数 `parameter.tts.vcn`；长文本是 `/v1/private/dts_create`，参数 `parameter.dts.vcn`。`x6_*`代表发音人代次，不是/v6接口。当前生成器只接在线产品，已知其他产品ID会在发送前拒绝。
- 腾讯基础/长文本使用2019-08-23云API，Action分别为TextToVoice/CreateTtsTask；实时是TextToStreamAudioWS专用WebSocket，没有云API Version参数。
- 阿里Qwen-TTS非实时、Qwen实时、CosyVoice、Qwen-Audio是不同协议和模型目录；即使相同音色ID，也要按模型选择记录。当前生成器只接48个qwen3-tts-flash音色。
- Polly记录 `supported_engines`，生成前检查VoiceId与engine。官方可用音色表的Patrick、Alba、Raúl尚未出现在此次取得的API枚举中，保留为不可生成候选，不猜测Raul等替代拼写。
- Azure公开表包含HD及多说话人音色。当前客户端ShortName校验不接受部分特殊名称，此类 `runnable=false`；全球表不保证当前区域可用。
- MiniMax系统表只列ID、名字和语言，没有逐音色的模型兼容矩阵，不能据此断言327个音色均适配所有speech-*模型。账号get_voice与当前授权优先。

`runnable=true`表示当前客户端实现了该条目的协议，不表示已实测账号权限或音质。新增目录没有调用付费合成API。接口映射未知的记录保留null，并标记不可生成。

## 用户MiniMax Excel逐条核对

输入：`20240620_Minimax 新增音色.xlsx`，Sheet1第1行为表头，第2–73行为资料。第68行只有“星野音色id.xlsx”提示，不是音色，因此有效ID为71个。

- 原327条官方目录中，10个ID完全匹配；61个不存在。
- 完全匹配的10条保留官方来源，并附 `historical_sources`，补存原表的性别、年龄组、描述及行号，不覆盖官方介绍。
- 缺少的61条已补入 [minimax-voices.json](minimax-voices.json)，标记 `source_kind=local_historical`、`verified_at=null`、`runnable=false`，接口配置为 `minimax.archive.unresolved`；原始描述放 `local_description`。
- “机械战甲”“搞笑大爷”“花甲奶奶”与当前官方表存在同名不同ID，只记录差异，不自动建立ID别名。

逐条结果及输入SHA-256见 [minimax-spreadsheet-audit.json](minimax-spreadsheet-audit.json)。原Excel没有编辑；核对副本仅在被Git忽略的test目录中保留。表格没有提供API/模型版本，并含星野提示，不能据此确认61个旧ID当前仍可由MiniMax公开接口调用。

## 仍存在的缺口

- 讯飞在线产品的完整授权列表仍需控制台：公开在线API文档只有候选；不能将64个超拟人音色直接移作在线v2音色。
- 火山其余284条跨产品记录仍缺完整资源/接口映射，保留 `volcengine.other.unresolved`，不按ID后缀猜版本。
- 百度仅覆盖当前短文本参数表44条；长文本、复刻及更多控制台音库未同步。
- ElevenLabs、Fish、Cartesia的账号库和私有/共享范围依账号而定，没有在缺少密钥时伪造全量快照；现有实时查询保留分页。
- 本轮没有加入缺少公开官方ID证据的新供应商，也没有验证全部账号权限或进行音质排名。

## 重建与来源

项目根目录执行：

```bash
python3 test/fetch_voice_sources.py
python3 test/build_voice_catalogs.py
python3 -m unittest discover -s test -p 'test_*.py'
```

原始网页与厂商Excel仅保存在本机test目录，不分发第三方整篇文档。下载/解析失败不会重建覆盖references目录；构建阶段全部解析和接口关联校验成功后才发布JSON。重建日期为固定快照日期，刷新时须重新核查并更新。用户Excel缺失时保留已有归档条目。

官方来源：[讯飞在线](https://www.xfyun.cn/doc/tts/online_tts/API.html)、[讯飞超拟人](https://www.xfyun.cn/doc/spark/super%20smart-tts.html)、[讯飞长文本](https://www.xfyun.cn/doc/tts/long_text_tts/API.html)、[Qwen-TTS](https://help.aliyun.com/zh/model-studio/qwen-tts-voice-list)、[CosyVoice](https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list)、[Qwen-Audio及基础音色Excel](https://help.aliyun.com/zh/model-studio/qwen-audio-tts-voice-list)、[腾讯三产品表](https://cloud.tencent.com/document/product/1073/92668)、[Azure全球表](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)、[Google完整表](https://docs.cloud.google.com/text-to-speech/docs/voices)、[Polly音色/引擎表](https://docs.aws.amazon.com/polly/latest/dg/available-voices.html)、[Polly API枚举](https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html)、[MiniMax系统表](https://platform.minimax.cn/docs/faq/system-voice-id)。其余已保留目录的原始来源和日期见各JSON；不把旧音色快照标成新抓取。

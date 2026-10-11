# 验证记录

日期：2026-10-10。

- Python 3.9.13 与 macOS 自带 Python 3.9.6 均运行客户端测试成功，16项全部通过。
- skill-creator quick_validate：Skill is valid。
- 新增/相关15个文本与JSON文件UTF-8解码通过；`.agents/skills/alltts`正确链接项目内技能。
- 官方目录：火山578条记录、573个唯一ID，其中294条第一表2.0 TTS记录；MiniMax327条/327个ID；Gemini30条/30个ID。
- 本机 `say` 枚举183个命令可用音色，其中9个zh_CN音色。
- `generate --provider system --voice Tingting --format aiff`真实生成 `test/output/system-zh.aiff`，42个字符。
- FFprobe：时长9.062132秒，22050 Hz、单声道、pcm_s16be，403736字节。
- FFmpeg完整解码成功，并转为`test/output/system-zh.mp3`供试听；此次未进行人耳听感验收。
- 云端测试仅使用模拟响应：未读取其他项目密钥，未调用计费合成/音色账号API。
- Windows/Linux分支未在对应系统执行。

## P1 本轮验证

- Python 3.9.13 和 macOS 自带 Python 3.9.6 上共34项离线测试全部通过（原16项+新增18项），未调用真实云端接口。
- 百炼：按官方非流式HTTP协议测试北京/新加坡地址、UTF-8文稿、语言、官方模型/音色/长度边界、业务错误、完整WAV URL下载、不转存裸PCM。
- 腾讯：官方TC3示例固定向量签名一致；实际发送UTF-8正文与签名字节一致；业务错误、原生语速、文本限制、MP3/WAV与整数VoiceType验证通过。
- Azure：SSML的中文及特殊字符转义、速率、风格支持校验、输出格式和区域音色列表字段保留通过。
- ElevenLabs：MP3字节响应、精确voice_id、账号音色分页、描述保留、has_more和缺失/重复token防护通过。
- 四家HTTP错误和网络超时均无自动重试；空/错误音频不发布输出；凭据脱敏通过。
- 命令行帮助和百炼/腾讯中文目录过滤通过。Azure/ElevenLabs静态查询会明确引导使用账号实时查询。
- 官方HTML快照保留在 `test/qwen-official.html` 和 `test/tencent-official.html`，构建脚本为 `test/build_p1_catalogs.py`。百炼48个非实时系统音色；腾讯67条去重官方记录。
- 本轮仍未进行真实云端合成、真实账号查询及听感验收。

## 2026-10-11 剩余7家验证

- Python 3.9.13 项目 `.venv` 安装固定版本 boto3/botocore 1.38.46、websocket-client 1.8.0及传递依赖，`pip check`通过。
- 全部56项离线测试通过（原34项+新增22项），不调用真实云端接口。
- OpenAI：官方Speech请求、语速/instructions、模型/音色限制与4096字符边界。
- Fish：model header/reference_id协议、工作空间自有模型分页、重复页/窗口受限防护。
- 讯飞：UTC签名日期与HMAC鉴权、UTF-8正文、空data帧、分块音频合并、PCM封装WAV、业务错误/超时/提前断连关闭连接。
- Google：OAuth/配额项目header、LINEAR16完整WAV、语言代码、5000 UTF-8字节限制、默认不传speakingRate和Chirp语速保护。
- Polly：真实SDK的Botocore Stubber验证合成参数、音频读取与关闭、PCM封装、区域音色分页；SDK配置明确关闭自动重试，只使用显式环境凭据。
- 百度：token交换、双重URL编码中文及+&%特殊字符、音频Content-Type校验、JSON业务错误、GBK字节上限与不支持字符拒绝。
- Cartesia：2026-08-14 Bearer协议、新版voice字符串、MP3/WAV结构与游标分页。
- 新增7家HTTP错误/超时、空音频失败清理、凭据脱敏均通过；CLI帮助和OpenAI/百度/讯飞目录过滤通过。
- 当前7家所需环境变量均未配置；没有真实账号音色查询、计费合成、解码或试听验收。离线字节样本不是可试听样音。
- 讯飞官方示例使用脱敏secret，其示例signature不能作为实际密钥的黄金向量；测试用固定测试凭据核查UTC日期和签名字符串。

## 2026-10-11 开源发布审查

- Python 3.9.13：65项离线测试与 pip check 通过。
- 新增9项安全回归：HTTP重定向拒绝、HTTPS限制、编码凭据脱敏、异常输出不回显、Gemini官方原始REST结构、元数据竞争与写入失败清理、Polly端点覆盖拒绝、讯飞重定向不发送文稿。
- 本次macOS真实生成中文AIFF：4.313651秒，22050 Hz、单声道、pcm_s16be；FFmpeg完整解码通过，测试临时文件已清理。无人耳听感验收，无云端计费调用。
- 原始第三方网页/PDF和本地语音目录只保留在开发者本机，不随开源仓库发布。
- 发布文件及Git历史使用Gitleaks 8.30.1脱敏扫描。CI运行Python3.9/3.13离线测试与完整历史密钥扫描。

# 贡献指南

欢迎改进中文音色选型、厂商接入和安全性。先阅读 README 中的功能边界；较大的新功能可先开 Issue 说明用途。

## 本地检查

Python 3.9+。可选依赖在虚拟环境中安装，新增依赖前核查 Requires-Python；如果需要更高 Python 版本，明确更新兼容范围与 CI，不能只创建一个仍使用 3.9 的虚拟环境。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r skills/alltts/requirements-optional.txt
python -m pip check
python -m unittest discover -s test -v
```

所有新增测试放在 `test/`。文件保存为 UTF-8，涉及中文的 JSON 使用 `ensure_ascii=False`。测试使用模拟响应，不注入真实密钥、不调用计费 API。

## 新增厂商或更新目录

- 从厂商官方文档核查认证、接口、模型、音色、分页和输出格式，记录来源 URL 与核查日期。
- 基础分支在 `skills/alltts/scripts/alltts.py`，扩展厂商在 `extra_providers.py`；复杂依赖仅在调用对应厂商时加载。
- 明确字段适用范围，不假设跨厂商语速或音色 ID 等价。不自动重试、不自动换厂商。
- 测试成功、业务错误、超时、分页重复、格式不符、覆盖保护和凭据不回显。真实云端验收需另有授权与记录，不能用模拟成功替代。
- 目录放在 `skills/alltts/references/`，保留来源、权限范围与可调用状态。官方描述与场景推断分别记录；不发布无授权的克隆声音 ID。
- 本地原始网页/PDF 快照不随仓库发布。`test/build_p1_catalogs.py` 是可选重建工具；使用前按脚本中的官方 URL 自行取得 `test/qwen-official.html` 和 `test/tencent-official.html`，离线测试不依赖这些文件。

提交前检查待提交文件，运行密钥扫描，不上传 `.env`、凭据、音频、私人文稿、虚拟环境或原始厂商文档。PR 说明行为变化、官方依据、测试结果和仍未验证的部分。

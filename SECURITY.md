# 安全说明

## 凭据使用

只在本机环境变量或 GitHub 等宿主的 Secret 管理中配置所需厂商凭据。`.env.example` 保持空值；真实 `.env` 不提交。客户端不读取其他项目密钥，也不会自动加载 `.env`。文稿和认证请求会发到你选择的厂商，请依据该厂商隐私政策选择内容。

当前防护包括：HTTPS 请求、禁用 HTTP/WebSocket 自动重定向、忽略 Polly 自定义端点、固定错误消息、对已配置凭据及其常见编码形式脱敏、忽略本地生成物、发布前与 CI 中的 Gitleaks 扫描。源码示例中的 `test-*`、`dummy-*` 为离线测试占位符。

这些措施不构成对所有环境的绝对保证：宿主日志、代理、被感染的操作系统、用户主动提交的新文件，仍需自行管理。音频内容和实时音色目录也可能有隐私信息，分享前检查。不要把凭据放进文稿、音色参数或文件名。

## 发布前自检

1. 检查 `git diff --cached` 与 `git ls-files`，确认没有真实凭据、文稿或私人音频。
2. 使用 Gitleaks 扫描待提交文件与 Git 历史；不要公开未经脱敏的扫描报告。
3. 运行 `python -m unittest discover -s test -v`。
4. `.gitignore` 无法移除已经提交的秘密。若密钥曾泄露，先在厂商控制台撤销/轮换，再处理 Git 历史；删除文件并不够。

## 报告漏洞

请使用仓库 [Security advisories](https://github.com/liaocaoxuezhe/all_tts/security/advisories) 中的 **Report a vulnerability** 私密报告。不要在公开 Issue 或 PR 里粘贴真实 Key、完整签名 URL、账号数据或私人文稿。可以附不含凭据的最小复现和影响范围。

# 会员授权与本地分析

ResearchDesk 使用本应用的官方 Sign in with ChatGPT 授权，将用户自己的会员推理权限交给配置的本地或远程执行主机。不读取 Codex、浏览器或其他应用的登录令牌，不自动切换 API Key 计费。账户资格、模型目录和限流以实际授权及服务返回为准，不由仓库预设。

## 准备与登录

在仓库根目录执行：

```sh
python3 -m venv .venv-membership
.venv-membership/bin/python -m pip install -r workflows/requirements-membership.txt
researchdesk_profile_dir="$HOME/Library/Application Support/ResearchDesk/chatgpt"
.venv-membership/bin/python scripts/membership.py --profile-dir "$researchdesk_profile_dir" status
.venv-membership/bin/python scripts/membership.py --profile-dir "$researchdesk_profile_dir" login
.venv-membership/bin/python scripts/membership.py --profile-dir "$researchdesk_profile_dir" models
```

Python 需为 3.9+。`--profile-dir` 接收授权目录，必须位于仓库及 Obsidian Vault 外；远程主机使用自己的本地路径。用户亲自在官方浏览器页面完成登录与用量授权，不提供密码或验证码。登录文件限制为当前用户可读写，不能上传 GitHub、复制进回执或放入 GitHub Secrets。

浏览器无法自动打开时，可用 `--manual-browser login`。进程在仓库外生成权限 `0600` 的临时 `authorization.json`，包含待打开的官方授权链接；授权完成后自动清理。不要提交该文件或将授权链接公开。

后端核验 PKCE、回调及 ID Token 的签名、发行者、受众、时效和 nonce；登录后还要求会员推理权限 `chatgpt.tokens.use.direct`。账户目录至少包含两个不同的可用模型，配置的生成与独立审阅模型须分别可用。看到模型列表不等于该账户真实推理已成功，更不表示官方剩余额度已知。

## 接入执行器

在本地 `config/local/workbench.yaml` 的 `runtime` 部分选择外部 venv 和会员 profile，随后按[自托管部署说明](self-hosted-worker.md)执行一条 `python scripts/workbench.py start` 注册并启动执行器。`membership.profile: null` 使用这台主机的 ResearchDesk 默认授权目录，不读取其他应用授权。

```sh
gh workflow run researchdesk-manual.yml --ref main -f operation=health
```

健康检查校验授权与配置模型，不进行推理。实际研究、确认选题和写作入口统一见[操作说明](README.md)；不要同时从 Vault、第二个克隆或其他主机启动会员任务。

## 调用与恢复

每次请求先保存不可变预留，再记录实际模型、完整响应终态及可获得的 usage；预算来自[共享策略](membership-budget.md)，包括失败和结果未知的请求。只有完整 `response.completed` 才能作为生成或审阅结果。客户端时间和输出字符上限不能当作服务端 token 或会员费用的硬上限。

研究模型和独立审阅模型读取同一绑定的原始证据，在独立上下文中执行；必须使用不同的实际模型 ID。当前默认全文模式在获取不完整时跳过候选，不用摘要冒充全文；其他显式模式仍须如实声明阅读范围，不能据摘要声称核验了论文全文、实验或行业趋势。

同一输入恢复原轮次，复用已核实检查点，不换 ID 重置额度。授权撤销、限流、网络中断、超时或终态未知时保留原预留并停止；先核对实际状态，不自动重发。缺少可核实 token、余额、会员等级或费用信息时保持未知。

实现所依据的官方说明：[授权流程](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)、[模型与推理](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)、[错误与恢复](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)。

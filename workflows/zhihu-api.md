# 知乎官方 API 接入

本入口只验证官方凭证、查询额度并发现候选，不调用模型，不写研究资料，不启动定时任务。它尚未接入 Research 批次的全文采集，不能仅在 `default.yaml` 添加 `adapter: zhihu` 就运行完整研究。

## 已核实的能力

2026-10-31 在[官方文档中心](https://developer.zhihu.com/docs)核对：

| 接口 | 用途与边界 |
| --- | --- |
| [额度查询](https://developer.zhihu.com/docs?key=quota) | `GET /api/v1/quota`；查询不消耗业务额度，实际限免余额以账号查询为准 |
| [知乎搜索](https://developer.zhihu.com/docs?key=zhihu_search) | `GET /api/v1/content/zhihu_search`；返回问题、回答或文章的候选，`ContentText` 是摘要，每次最多10条，当前 `HasMore` 固定为 `false` |
| [问题回答](https://developer.zhihu.com/docs?key=question_answers) | 返回回答摘要或截取文本，不代表回答全文；本客户端暂不调用 |
| [我的创作全文](https://developer.zhihu.com/docs?key=user_content_detail) | 仅支持当前 Access Secret 所属账号本人已发布的内容；不能用于读取任意第三方文章或回答，本客户端暂不调用 |

搜索请求使用 `Authorization: Bearer <access_secret>`、秒级 `X-Request-Timestamp` 和 `Content-Type: application/json`。额度文档要求客户端与服务器时间相差不超过10分钟。站内搜索不要求先实现用户 OAuth，用户内容授权是另一类能力。

## 获取凭证

1. 打开[官方个人中心](https://developer.zhihu.com/profile)，自行完成知乎登录。新账号注册、平台协议、实名或其他资格步骤按实际页面处理。
2. 在个人中心查看 Access Secret 及「用量统计」中的搜索限免额度。具体资格和额度不能从文档默认值推断。
3. 不要把 Secret 发到聊天、截图或仓库。下面的交互命令会在本机隐藏输入，只在本次进程使用，不保存到文件。

```sh
python3 -B scripts/researchdesk_zhihu.py quota --prompt-secret
```

后续自托管部署可以由运行环境提供 `ZHIHU_ACCESS_SECRET`；凭证留在仓库和 Obsidian Vault 外。命令不接受直接传入 Secret 的参数，避免进入 shell 历史和进程命令行。不要把凭证粘贴进 YAML 或写进命令示例。

## 小规模候选验证

```sh
python3 -B scripts/researchdesk_zhihu.py search \
  --query '大模型 Agent 记忆' --count 5 --days 60 --prompt-secret
```

每次先查询搜索免费余额，缺失或不足时停止，不主动选择付费回落；仅发起一次搜索，不自动重试。平台会在免费额度用尽后依次使用体验余额和充值余额，因此预查询仍存在并发或其他客户端消耗额度的竞态，不能当成平台提供的零扣费保证。价格与规则见[服务价格](https://developer.zhihu.com/docs?key=billing_price)；本工具不充值、不调用直答或其他生成服务。

候选按创建时间过滤近60天，再在本次有限结果内按赞同、评论排序；不等于取得过去两个月全站最热内容。没有可靠创建时间的条目不会被认定为新发表，更新旧文也不会仅凭 `EditTime` 混入新文窗口。

输出为 JSON，标注 `discovery_only`、摘要阅读范围和扫描限制，不自动写文件。保留 API 返回的溯源链接，另生成去除追踪参数的规范链接用于去重。数字内容 ID 保留字符串精度，避免长 ID 损坏。请求头、Secret 和原始错误响应不进入输出或资料归档。

## 接入完整研究前仍需完成

搜索摘要只作为发现线索，不能转换成 `full_text_required` 的合格原文。需要先验证可访问且允许读取的公开正文、作者提供的原始博客，或获准的内容导入方式；实际取得完整正文后，才能对接现有 URL 去重、正文归档和 Research/Insight。

当前没有核实到可用本账号 Secret 读取任意第三方全文的上述接口。用户 OAuth、收藏列表或搜索结果本身都不能据此推导出第三方全文权限。正文不可得时保留为候选，不制造全文研究结果。

## 离线检查

```sh
PYTHONPATH=tests python3 -B -m unittest test_zhihu -v
git diff --check
```

测试使用虚构官方响应，不连接知乎，不消耗搜索额度或模型用量。账号资格、当前免费额度与真实响应仍需用户完成登录后小批验证。

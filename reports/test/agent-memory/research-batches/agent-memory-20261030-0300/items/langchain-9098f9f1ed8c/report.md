# Context Engineering: How Deep Agents Remember：研究批次测试

> TEST：官方 ChatGPT 会员真实研究与独立审阅；仅博客节选，未核验完整原文或实现；未正式入库。

- 来源：[Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)。
- 资料标识：`blog-05c33166-b18e-425e-91e0-36ddd26f21aa`；已有资料：`sources/blogs/agent-memory/blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md`。
- 覆盖范围：仅博客节选，未核验完整原文或实现。
- 研究模型：`gpt-6-luna`；独立审阅：`gpt-6.1-sol`。
- 审阅：`pass`；修订次数：1；原始材料仅在内存中提供给模型。

## 研究概述

本概述仅覆盖所提供的 LangChain 博客节选，聚焦其描述的代理上下文管理方法；不代表对相关实现或效果的独立核验。

## 主张与证据

- **作者声称（未独立核验）**：节选将上下文工程概括为两类做法：阻止不必要的信息进入上下文窗口，以及管理和筛选已经进入窗口的信息。（[A7](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **作者声称（未独立核验）**：节选称 Deep Agents 通过卸载、摘要、按需加载技能、子代理和长期记忆等方式管理上下文；其中长期记忆会将代理学到的信息保存到可跨对话使用的文件中。（[A9、A10、A11、A12、A13、A14](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **作者声称（未独立核验）**：节选称，工具结果超过约 20,000 个 token 时会先写入文件，模型收到简短预览和文件路径；超大用户消息也会被类似处理，但阈值更高。（[A25、A26、A28](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **作者声称（未独立核验）**：节选称，默认在上下文使用量达到模型窗口的 85% 后，摘要中间件会通过一次单独的 LLM 调用压缩较早消息，移除旧消息并保留最近消息原文。（[A31、A32](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **我们的推断**：按节选的描述，卸载主要减少大型单次输入带来的上下文增长，摘要则用于处理长任务中的累积；两者处理的是不同时间尺度的上下文负担。（[A25、A30、A31](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）

## 局限

- 本次只读博客节选，未核验全文、实验或实现。
- 节选描述了机制及默认阈值，但未提供可独立验证的性能、可靠性、隐私或安全性评测。

## 独立审阅

逐项核查、证据摘要与实际用量见同目录检查点及单项回执。

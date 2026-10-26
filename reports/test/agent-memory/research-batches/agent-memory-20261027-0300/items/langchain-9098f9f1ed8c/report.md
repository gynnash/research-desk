# Context Engineering: How Deep Agents Remember：研究批次测试

> TEST：官方 ChatGPT 会员真实研究与独立审阅；仅博客节选，未核验完整原文或实现；未正式入库。

- 来源：[Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)。
- 资料标识：`blog-05c33166-b18e-425e-91e0-36ddd26f21aa`；已有资料：`sources/blogs/agent-memory/blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md`。
- 覆盖范围：仅博客节选，未核验完整原文或实现。
- 研究模型：`gpt-6-luna`；独立审阅：`gpt-6.1-sol`。
- 审阅：`pass`；修订次数：0；原始材料仅在内存中提供给模型。

## 研究概述

本次仅覆盖 LangChain 博客提供的节选，讨论 Deep Agents 如何管理运行中的上下文以缓解节选所称的“context rot”；这涉及长期记忆，但内容主要聚焦上下文管理机制，不能据此判断其完整记忆架构或实际效果。

## 主张与证据

- **作者声称（未独立核验）**：作者认为，长任务会累积指令、工具结果和文件等信息；上下文过多、历史与噪声增加，可能不利于模型准确性和推理。（[A3、A4、A5](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **原文事实**：节选将上下文管理分为两类：阻止不必要信息进入上下文，以及管理和筛选已经进入上下文的信息。（[A7](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **原文事实**：节选称 Deep Agents 使用文件卸载、对话摘要、按需加载技能、子代理和跨会话文件记忆等方式管理信息。（[A9、A10、A11、A12、A13、A14](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **作者声称（未独立核验）**：节选描述的卸载机制会在工具结果超过约 20,000 tokens 时将完整结果写入文件，并向模型提供预览和路径；超长用户消息也会以较高阈值另行保存。（[A25、A26、A28](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）
- **作者声称（未独立核验）**：节选称摘要中间件默认在上下文使用量达到模型窗口的 85% 后调用另一个 LLM 压缩较早消息，并保留最近消息原文。（[A31、A32](https://www.langchain.com/blog/context-engineering-deep-agents-remember)）

## 局限

- 仅阅读博客节选，未核验全文、实现代码、实验或实际部署效果。
- 节选中的机制和阈值是作者的描述；材料未提供独立验证，也未报告这些方法对准确性或推理质量的量化影响。
- 节选未充分说明长期记忆文件的写入、检索、更新、遗忘、隐私与安全策略。

## 独立审阅

逐项核查、证据摘要与实际用量见同目录检查点及单项回执。

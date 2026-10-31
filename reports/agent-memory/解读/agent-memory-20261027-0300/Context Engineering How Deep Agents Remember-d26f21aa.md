---
title: 'Context Engineering: How Deep Agents Remember'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261027-0300-update-blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md", "original_sha256": "ed96eb763f435988ae1a58b8fa39ec135969bdc407d30e86b2098e30fc35b0bc", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Context Engineering: How Deep Agents Remember

本次仅覆盖 LangChain 博客提供的节选，讨论 Deep Agents 如何管理运行中的上下文以缓解节选所称的“context rot”；这涉及长期记忆，但内容主要聚焦上下文管理机制，不能据此判断其完整记忆架构或实际效果。

## 问题、方法与结果

作者认为，长任务会累积指令、工具结果和文件等信息；上下文过多、历史与噪声增加，可能不利于模型准确性和推理。

节选将上下文管理分为两类：阻止不必要信息进入上下文，以及管理和筛选已经进入上下文的信息。

节选称 Deep Agents 使用文件卸载、对话摘要、按需加载技能、子代理和跨会话文件记忆等方式管理信息。

节选描述的卸载机制会在工具结果超过约 20,000 tokens 时将完整结果写入文件，并向模型提供预览和路径；超长用户消息也会以较高阈值另行保存。

节选称摘要中间件默认在上下文使用量达到模型窗口的 85% 后调用另一个 LLM 压缩较早消息，并保留最近消息原文。

## 如何理解这些结论

仅阅读博客节选，未核验全文、实现代码、实验或实际部署效果。

节选中的机制和阈值是作者的描述；材料未提供独立验证，也未报告这些方法对准确性或推理质量的量化影响。

节选未充分说明长期记忆文件的写入、检索、更新、遗忘、隐私与安全策略。

## 来源与阅读范围

- [Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)：仅阅读正文节选，未覆盖全部原文。

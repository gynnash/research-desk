---
title: 'Context Engineering: How Deep Agents Remember'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/agent-memory-20261030-0300-update-blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md", "original_sha256": "948473f78edfee4051a458065149f9c118bdb25378b73da87e245b70026adc04", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Context Engineering: How Deep Agents Remember

本概述仅覆盖所提供的 LangChain 博客节选，聚焦其描述的代理上下文管理方法；不代表对相关实现或效果的独立核验。

## 问题、方法与结果

节选将上下文工程概括为两类做法：阻止不必要的信息进入上下文窗口，以及管理和筛选已经进入窗口的信息。

节选称 Deep Agents 通过卸载、摘要、按需加载技能、子代理和长期记忆等方式管理上下文；其中长期记忆会将代理学到的信息保存到可跨对话使用的文件中。

节选称，工具结果超过约 20,000 个 token 时会先写入文件，模型收到简短预览和文件路径；超大用户消息也会被类似处理，但阈值更高。

节选称，默认在上下文使用量达到模型窗口的 85% 后，摘要中间件会通过一次单独的 LLM 调用压缩较早消息，移除旧消息并保留最近消息原文。

按节选的描述，卸载主要减少大型单次输入带来的上下文增长，摘要则用于处理长任务中的累积；两者处理的是不同时间尺度的上下文负担。

## 如何理解这些结论

本次只读博客节选，未核验全文、实验或实现。

节选描述了机制及默认阈值，但未提供可独立验证的性能、可靠性、隐私或安全性评测。

## 来源与阅读范围

- [Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)：仅阅读正文节选，未覆盖全部原文。

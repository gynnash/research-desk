---
title: 'Context Engineering: How Deep Agents Remember'
kind: reading_note
topics:
- agent-memory
---

<!-- researchdesk-reading {"derived_from": "reports/agent-memory/cycle-agent-memory-gh-20261019-research-blog-05c33166-b18e-425e-91e0-36ddd26f21aa.md", "original_sha256": "0a5293847491db21ff15b4c88eec4b8afce0e6bcbcb52e08a5e705af8fdac24d", "presentation": "reviewed_content_reformatted"} -->

[返回研究首页](../../../../%E7%A0%94%E7%A9%B6%E9%A6%96%E9%A1%B5.md)

# Context Engineering: How Deep Agents Remember

基于所提供的 LangChain 博客节选，概述其对智能体上下文管理及 Deep Agents 中相关机制的介绍；不代表对系统效果或实现的独立核验。

## 问题、方法与结果

节选将上下文管理分为减少无关信息进入上下文，以及管理和筛选已在上下文中的信息两类。

节选称 Deep Agents 可通过文件卸载、摘要、按需加载技能、子代理和跨对话文件记忆等方式，将部分信息移出主智能体的活动上下文。

节选描述的工具结果卸载流程会在结果超过约 20,000 个 token 时将其写入文件，并向模型提供简短预览和文件路径；较大的用户消息采用更高阈值处理。

节选称摘要中间件默认在上下文使用量达到模型窗口的 85% 后压缩较早消息，同时保留最近消息原文。

## 如何理解这些结论

本次只读博客节选，没有核验全文、实验或实现。

节选中的阈值与机制描述属于作者陈述，未独立验证其当前适用性、实际运行表现或记忆准确性。

## 来源与阅读范围

- [Context Engineering: How Deep Agents Remember](https://www.langchain.com/blog/context-engineering-deep-agents-remember)：仅阅读正文节选，未覆盖全部原文。

# Why Memory Isn't a Plugin：研究批次测试

> TEST：官方 ChatGPT 会员真实研究与独立审阅；仅博客节选，未核验完整原文或实现；未正式入库。

- 来源：[Why Memory Isn't a Plugin](https://www.letta.com/blog/why-memory-isnt-a-plugin/)。
- 资料标识：`blog-56521361-c491-428a-b75e-3c92c603161e`；已有资料：`sources/blogs/test/agent-memory/blog-56521361-c491-428a-b75e-3c92c603161e.md`。
- 覆盖范围：仅博客节选，未核验完整原文或实现。
- 研究模型：`gpt-6-luna`；独立审阅：`gpt-6.1-sol`。
- 审阅：`pass`；修订次数：0；原始材料仅在内存中提供给模型。

## 研究概述

本次仅依据所提供的 Letta 博客节选，概述作者关于智能体记忆与 harness（智能体运行框架）关系的观点；不代表对其技术主张或产品描述的独立验证。

## 主张与证据

- **作者声称（未独立核验）**：作者认为，上下文管理是 harness 的核心职责，而智能体记忆建立在 harness 对上下文与状态的管理之上，因此记忆不宜被视为可随意插入的插件。（[A2、A3、A24](https://www.letta.com/blog/why-memory-isnt-a-plugin/)）
- **作者声称（未独立核验）**：作者主张，对过往会话数据进行 RAG 检索可以作为插件，但检索只是记忆的一小部分；其文中也称 MemGPT 是有状态的智能体 harness，而非单纯的 RAG 或可插拔记忆工具。（[A5、A7、A8](https://www.letta.com/blog/why-memory-isnt-a-plugin/)）
- **作者声称（未独立核验）**：作者指出，提示词重写、外部状态管理及 harness 自身的上下文管理，共同构成其所描述的 MemGPT 记忆机制；不同 harness 对上下文加载、压缩后保留内容和交互存储等问题有不同处理方式。（[A9、A10、A13、A14、A18](https://www.letta.com/blog/why-memory-isnt-a-plugin/)）
- **作者声称（未独立核验）**：作者称 Letta Code 将记忆映射到由 Git 支持的文件系统，并允许专门负责提示词重写与主动记忆管理的后台子智能体并发修改。（[A22](https://www.letta.com/blog/why-memory-isnt-a-plugin/)）

## 局限

- 本次只读博客节选，没有核验全文、实验或实现。
- 节选中的系统设计与产品能力描述属于作者陈述，未在材料中提供独立验证。
- 材料未给出所述架构的评测数据，不能据此判断其相对效果、可靠性或隐私与安全表现。

## 独立审阅

逐项核查、证据摘要与实际用量见同目录检查点及单项回执。

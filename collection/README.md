# 采集原文

按研究方向保存实际取得的论文与博客原文。方向来自 [research_topics.yaml](../config/research_topics.yaml)，当前默认是 [Agent Memory](agent_memory/README.md)。

每次采集保存在方向下独立的批次目录，`items/<资料 ID>/original.md` 为可读原文；同目录的 YAML 用于精确重放，批次 `manifest.yaml` 列出实际取得的资料、来源与原文路径。

只发现链接或摘要不等于已经取得原文。完整原文采集成功后，才能交给 Research 逐篇研究；总结另存到 [summary](../summary/README.md)。操作见[采集说明](../workflows/collection.md)。

# 恢复范围与来源

本仓库根据 Yanzhi Bao 的 `Appendix A: Source Code and UNIX Orchestration Scripts` 整理，参考毕业设计 `Optimising an Offline Voice AI Pipeline for Low-Latency Interaction on Resource-Constrained Edge Hardware`。这是事后恢复版本，没有恢复历史 Git 提交，也没有附带原始实验结果。

| 附录位置 | 原始内容 | 本仓库处理 |
|---|---|---|
| 第 2–3 页 | Ubuntu、ALSA、whisper.cpp、llama.cpp、Piper 环境命令 | 整理为 SETUP.md；没有自动升级系统或安装软件 |
| 第 4–5 页 | HTTP 基线客户端 | 保留录音 → ASR HTTP → LLM HTTP 顺序，补请求超时与错误检查 |
| 第 6–7 页 | Bash 串行 NOVA 主循环 | 保留 ASR → LLM → TTS 顺序及 Bash 入口，将进程管理移至可测试的 Python 标准库代码 |
| 第 6 页 | 调用 `vad_alsa.py`，没有该文件正文 | 新补 RMS 录音端点检测模块，不能当成原始 VAD 源码 |
| 第 8 页 | F16 转换与 Q4_K_M 量化 | 修复 PDF 换行破坏的命令，调整为 `convert_hf_to_gguf.py` 与 `llama-quantize` |
| 第 9 页 | CPU0 频率及 thermal_zone0 温度记录 | 保留采样功能；记录传感器类型，缺失值留空，避免误认温度为零或已发生降频 |

## 主要修订

1. 原主流程在每次识别后执行 `sudo ... drop_caches`；本版本移除这一步。清理系统页缓存不是模型内存管理的替代方法，也可能使后续加载变慢。
2. 不再使用固定 `/tmp/nova_buffer.wav`、`/tmp/nova_out.txt`；每轮使用独立目录，避免运行互相覆盖。
3. 不再用 `grep -v '['` 过滤 ASR 控制台输出；使用 whisper-cli 的文本输出文件。
4. 采用 TinyLlama Chat 显式提示模板；修改其他模型时需要相应修改模板。
5. 原附录使用 Piper 1.2 二进制，本版本默认适配 `python3 -m piper`，输出自带采样率的 WAV 交给播放器。
6. 不再传递旧 `--use-mmap` 标志；模型加载方式由实际安装的 llama.cpp 决定，需单独核实。
7. 新增超时、错误日志、阶段耗时及自动测试。这些是重建时补充的工程能力，不能描述为原实验已做的工作。

## 边界

- 附录没有提供 HTTP 服务端，因此 HTTP 基线并不完整，不能直接复现两种架构的内存对比。
- 报告提到的半流式输出在附录主脚本中没有实现。本仓库按附录恢复为完整回复后合成。
- 使用管道或本地子进程仍有 IPC、数据复制和模型加载成本，不能称为“零开销”。
- 没有用本仓库重新验证论文中的延迟、RTF、内存及温度结论。
- 本次新增 VAD 只是能量门限，噪声、音乐、键盘声也可能触发；不包含神经网络 VAD、目标说话人提取或降噪算法。

适合对外介绍为：**“毕业设计离线语音助手的代码整理与重建版本，保留原模型链路，补充可复现入口、日志和测试。”**

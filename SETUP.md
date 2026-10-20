# Linux 部署

目标环境为 Linux + Python 3.10+，CPU 推理。Windows 可运行单元测试和已有 WAV 流程（需自行准备兼容的后端），ALSA 麦克风录音只支持 Linux。

## 1. 基础工具

在确认本机需要后自行安装：

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake git python3-venv ffmpeg alsa-utils
python3 -m venv .venv
source .venv/bin/activate
python -m pip install piper-tts
mkdir -p third_party models
```

Piper 是可选外部依赖，不需要它也能运行本仓库测试。实际部署成功后，记录 Python 包版本及两个上游仓库的 commit；本重建版没有提供经过真实推理验证的依赖锁定版本。

## 2. 编译推理后端

```bash
git clone https://github.com/ggml-org/whisper.cpp.git third_party/whisper.cpp
cmake -S third_party/whisper.cpp -B third_party/whisper.cpp/build -DGGML_CUDA=OFF
cmake --build third_party/whisper.cpp/build --config Release -j 4

git clone https://github.com/ggml-org/llama.cpp.git third_party/llama.cpp
cmake -S third_party/llama.cpp -B third_party/llama.cpp/build -DGGML_CUDA=OFF
cmake --build third_party/llama.cpp/build --config Release -j 4
```

检查 `build/bin/whisper-cli --help` 和 `build/bin/llama-completion --help`。不同版本的 llama.cpp 命令名称及参数可能不同；本版本针对一次性 completion 接口，不能盲目替换成会进入交互界面的 CLI。

## 3. 模型文件

根据上游说明自行下载：

- whisper.cpp 英文 `base.en` 的 Q4_0 模型，配置中默认名 `ggml-base.en-q4_0.bin`。也可以使用其他兼容的 base.en 权重并改路径。
- `TinyLlama-1.1B-Chat-v1.0` 的 Q4_K_M GGUF。
- Piper `en_US-lessac-medium.onnx` **及同名 `.onnx.json`**。

Piper 的 voice 下载示例（会联网）：

```bash
cd models
python -m piper.download_voices en_US-lessac-medium
cd ..
```

下载来源与许可证以相应项目及模型卡为准。代码仓库不分发这些第三方文件。

## 4. 配置与输入

复制根目录配置，按本机修改路径；所有模型与输出相对路径基于**配置文件所在目录**解析。命令字段是参数数组，不是 shell 命令字符串。

```bash
cp config.example.json config.local.json
python -m nova check --config config.local.json
ffmpeg -i your_audio.mp3 -ar 16000 -ac 1 -c:a pcm_s16le input.wav
python -m nova run --config config.local.json --wav input.wav
```

Piper 命令默认 `python3 -m piper`，应在安装了 Piper 的虚拟环境中运行。`check` 仅检查程序路径及模型文件存在性，不保证模块已安装或权重有效。

麦克风调试：

```bash
arecord -l
aplay -l
python scripts/vad_alsa.py --out input.wav --device default
bash scripts/nova_pipeline.sh --config config.local.json --mic --play
```

默认 RMS 门限为 0.015，连续低能量约 800ms 结束（以 30ms 帧计，实际向上取整到 810ms）。门限应依据麦克风和背景噪声调整；它不是人声概率。提高静音等待能保留说话停顿，也会增加响应等待。长时间没有有效输入会超时。

## 5. 量化与监测

已有兼容 GGUF 时无需量化。自行转换需要完整 Hugging Face 权重及上游转换脚本依赖；量化机器需要足够内存与磁盘：

```bash
bash scripts/model_quantization_pipeline.sh third_party/llama.cpp /path/to/raw-tinyllama models/new-quantized
bash scripts/thermal_throttle_monitor.sh --out thermal_metrics.csv --samples 30
```

温度监测只记录指定 thermal zone，并不自动识别 CPU package，也不能凭高温确认降频。输出文件已存在时拒绝覆盖。

## 上游文档

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
- [whisper-cli 参数](https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/README.md)
- [llama.cpp completion](https://github.com/ggml-org/llama.cpp/tree/master/tools/completion)
- [Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md)
- [TinyLlama Chat 模型](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0)

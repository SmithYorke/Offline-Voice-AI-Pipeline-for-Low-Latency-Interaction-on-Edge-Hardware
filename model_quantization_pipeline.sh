#!/usr/bin/env bash
# Adapted from Appendix A. Run only after preparing upstream dependencies.
set -euo pipefail
if [[ $# -ne 3 ]]; then
  echo "Usage: bash $0 /path/to/llama.cpp /path/to/HF-TinyLlama /path/to/new-output-directory" >&2
  exit 2
fi
LLAMA_DIR="$1"
RAW_DIR="$2"
OUT_DIR="$3"
CONVERTER="$LLAMA_DIR/convert_hf_to_gguf.py"
QUANTIZER="$LLAMA_DIR/build/bin/llama-quantize"
[[ -f "$CONVERTER" && -x "$QUANTIZER" && -d "$RAW_DIR" ]] || {
  echo "Missing converter, compiled quantizer, or source model directory." >&2
  exit 1
}
if [[ -e "$OUT_DIR" ]]; then
  echo "Choose a new output directory to avoid overwriting models." >&2
  exit 1
fi
mkdir -p "$OUT_DIR"
"${NOVA_PYTHON:-python3}" "$CONVERTER" "$RAW_DIR" --outfile "$OUT_DIR/tinyllama-F16.gguf" --outtype f16
"$QUANTIZER" "$OUT_DIR/tinyllama-F16.gguf" "$OUT_DIR/tinyllama-Q4_K_M.gguf" Q4_K_M
echo "Quantized model: $OUT_DIR/tinyllama-Q4_K_M.gguf"

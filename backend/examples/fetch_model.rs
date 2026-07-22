// Forces the Qwen3-ASR model download (backend/models/, ~1.8GB) during
// install/build instead of on the first `run.sh` launch, so a slow
// connection doesn't get mistaken for a hung server by run.sh's
// READY_TIMEOUT_SECS. Safe to re-run: `from_pretrained` is a no-op if the
// model is already cached.
use qwen3_asr::AsrInference;
use std::path::Path;

fn main() {
    AsrInference::from_pretrained("Qwen/Qwen3-ASR-0.6B", Path::new("models/"), qwen3_asr::best_device())
        .expect("while downloading model");
    println!("Model ready.");
}

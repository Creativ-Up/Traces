use anyhow::{Context, Result};
use qwen3_asr::{AsrInference, TranscribeOptions};
use std::{io::Write, path::Path};

/// An object relying of `qwen3_asr` to transcript audio.
pub struct Transcription {
    engine: AsrInference,
}

/// A structure used to globally handle the transcription engine in Rocket.
pub struct TranscriptionState {
    transcription: Transcription,
}

impl Default for TranscriptionState {
    fn default() -> Self {
        let device = qwen3_asr::best_device();
        // let engine =
        //     AsrInference::load(&PathBuf::from(MODEL_PATH), device).expect("cannot create engine");
        let engine =
            AsrInference::from_pretrained("Qwen/Qwen3-ASR-0.6B", Path::new("models/"), device)
                .expect("while loading model");
        Self {
            transcription: Transcription { engine },
        }
    }
}

impl TranscriptionState {
    /// Returns the underlying transcription engine.
    pub fn transcription(&self) -> &Transcription {
        &self.transcription
    }
}

impl Transcription {
    /// Transcript the audio file in WAV format which file path is given by the parameter.
    pub fn transcript(&self, wav_path: &str) -> Result<String> {
        self.engine
            .transcribe(wav_path, TranscribeOptions::default())
            .context("while transcribing text")
            .map(|t| t.text)
    }

    /// Transcript raw WAV bytes by writing them to a temporary file first,
    /// since the underlying engine only reads audio from a file path.
    pub fn transcript_bytes(&self, wav_bytes: &[u8]) -> Result<String> {
        let mut file = tempfile::Builder::new()
            .suffix(".wav")
            .tempfile()
            .context("while creating temporary file")?;
        file.write_all(wav_bytes)
            .context("while writing audio to temporary file")?;
        let path = file
            .path()
            .to_str()
            .context("temporary file path is not valid UTF-8")?;
        self.transcript(path)
    }
}

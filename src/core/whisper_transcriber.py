import os
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class TranscriptionResult:
    success: bool
    text: str = ""
    segments: List[dict] = None
    error: str = ""

    def __post_init__(self):
        if self.segments is None:
            self.segments = []


class WhisperTranscriber:
    """Local faster-whisper model wrapper for speech-to-text"""

    SUPPORTED_MODELS = ["small", "medium", "large-v2", "large-v3"]

    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        models_dir: str = "models",
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.models_dir = models_dir
        self._model = None

    def initialize(self):
        """Load the whisper model"""
        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            error_msg = str(e)
            if "c10.dll" in error_msg or "WinError 1114" in error_msg or "DLL" in error_msg:
                raise RuntimeError(
                    f"PyTorch DLL 加载失败，可能是 Python 版本与 PyTorch 不兼容。\n"
                    f"原始错误: {error_msg}\n"
                    f"解决方法：\n"
                    f"pip uninstall torch torchvision torchaudio -y && "
                    f"pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu"
                ) from e
            raise

        # Determine compute type based on device
        if self.device == "cuda":
            compute_type = "float16"
        else:
            compute_type = self.compute_type

        # Check for local model first
        local_model_path = os.path.join(
            self.models_dir, f"faster-whisper-{self.model_name}"
        )

        if os.path.exists(local_model_path):
            model_path = local_model_path
        else:
            # Use model name for auto-download
            model_path = self.model_name

        self._model = WhisperModel(
            model_path,
            device=self.device,
            compute_type=compute_type,
        )

    def close(self):
        """Release model resources"""
        self._model = None

    def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        beam_size: int = 5,
    ) -> TranscriptionResult:
        """Transcribe audio file to text"""
        if not self._model:
            return TranscriptionResult(success=False, error="Model not initialized")

        if not os.path.exists(audio_path):
            return TranscriptionResult(success=False, error=f"Audio file not found: {audio_path}")

        try:
            segments, info = self._model.transcribe(
                audio_path,
                language=language,
                beam_size=beam_size,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
            )

            # Collect all segments
            segment_list = []
            text_parts = []

            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                })
                text_parts.append(segment.text.strip())

            full_text = "".join(text_parts)

            return TranscriptionResult(
                success=True,
                text=full_text,
                segments=segment_list,
            )

        except Exception as e:
            return TranscriptionResult(success=False, error=str(e))

    def is_initialized(self) -> bool:
        """Check if model is loaded"""
        return self._model is not None

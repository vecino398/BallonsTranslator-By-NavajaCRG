from .base import (
    DEFAULT_DEVICE,
    DEVICE_SELECTOR,
    OCR,
    OCRBase,
    TextBlock,
    postprocess_ocr_text,
    register_OCR,
)

# Módulos OCR adicionales — registro automático por decorador @register_OCR
try:
    from . import ocr_callisto_qwen2vl_2b
except Exception as e:
    import logging
    logging.getLogger("BallonsTranslator").debug(f"ocr_callisto_qwen2vl_2b not loaded: {e}")

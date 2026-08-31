"""
Callisto-OCR3-2B and Qwen2-VL-OCR-2B – fast 2B VLM OCR (Hugging Face). Issue #872.
- callisto_ocr: prithivMLmods/Callisto-OCR3-2B-Instruct
- qwen2_vl_ocr_2b: prithivMLmods/Qwen2-VL-OCR-2B-Instruct

Both use language-aware prompt: "Give me text from image, writen in {lang} language, nothing else."
Requires: pip install transformers torch pillow accelerate
"""
from typing import List, TYPE_CHECKING
import os
import re
import tempfile
import importlib.util
import numpy as np
import cv2
from .base import OCRBase, register_OCR, DEVICE_SELECTOR, TextBlock, OCR

if TYPE_CHECKING:
    # Solo para anotaciones de tipo; nunca se ejecuta en tiempo de arranque.
    from PIL import Image


def _heavy_deps_available() -> bool:
    """Comprueba si transformers/torch/pillow están instalados SIN importarlos.

    A diferencia de un `try: import torch` a nivel de módulo, esto no dispara
    la inicialización de CUDA ni el coste de import de transformers al arrancar
    BT — el import real solo ocurre en _load_model(), cuando el usuario
    selecciona y usa este motor de verdad.
    """
    for mod in ("torch", "transformers", "PIL"):
        if importlib.util.find_spec(mod) is None:
            return False
    return True


_VLM2B_AVAILABLE = _heavy_deps_available()
if not _VLM2B_AVAILABLE:
    import logging
    logging.getLogger("BallonsTranslator").debug(
        "Callisto/Qwen2-VL-OCR 2B not available. Install: pip install transformers torch pillow accelerate"
    )


SOURCE_LANGUAGES = [
    "English", "Japanese", "Korean", "Chinese", "Russian",
    "French", "German", "Spanish", "Italian", "Portuguese",
    "Arabic", "Hindi", "Vietnamese", "Thai", "Indonesian",
]


def _cv2_to_pil_rgb(img: np.ndarray) -> "Image.Image":
    from PIL import Image
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(img)


def _prompt_for_lang(lang: str) -> str:
    return (
        f"Transcribe all text visible in this image. "
        f"The language is {lang}. "
        f"Return only the extracted text exactly as written. "
        f"Do not explain. "
        f"Do not translate. "
        f"Do not describe the image. "
        f"Do not answer questions. "
        f"Only output the text."
    )


def _make_vlm_2b_ocr(module_key: str, model_id: str, description_short: str):
    """Factory for 2B VLM OCR modules (Callisto, Qwen2-VL-OCR-2B) with same API."""

    class _VLM2BOCR(OCRBase):
        params = {

            "preset": {
                "type": "selector",
                "options": [
                    "manual",
                    "callisto_rapido",
                    "callisto_equilibrado",
                    "callisto_precision",
                    "callisto_largo"
                ],
                "value": "callisto_equilibrado",
                "description": "Preset rápido para Callisto/Qwen2-VL OCR.",
            },
            "source_language": {
                "type": "selector",
                "options": SOURCE_LANGUAGES,
                "value": "French",
                "description": "Language of the text in the image (for OCR prompt).",
            },
            # Placeholder estático: NO llama a DEVICE_SELECTOR() aquí (eso importaría
            # torch y sondearía la GPU en el momento de definir la clase, es decir,
            # al arrancar BT). Se refresca con el valor real y perezoso en __init__.
            "device": {"type": "selector", "options": ["cpu"], "value": "cpu"},
            "crop_padding": {
                "type": "line_editor",
                "value": 4,
                "description": "Pixels around each crop (0–24).",
            },
            "max_new_tokens": {
                "type": "line_editor",
                "value": 512,
                "description": "Max tokens per block (128–2048).",
            },
            "use_bf16": {
                "type": "checkbox",
                "value": True,
                "description": "Use bfloat16.",
            },
            "description": description_short,

            "clean_edge_quotes": {
                "type": "checkbox",
                "value": True,
                "description": "Remove false quotes/apostrophes at the beginning and end of OCR text.",
            },

            "fallback_ocr": {
                "type": "selector",
                "options": [
                    "none",
                    "google_lens_exp"
                ],
                "value": "none",
                "description": "OCR used when Callisto fails.",
            },

        }
        _load_model_keys = {"processor", "model"}
        _model_id = model_id

        def __init__(self, **params) -> None:
            super().__init__(**params)
            # Aquí SÍ es seguro llamar a DEVICE_SELECTOR(): __init__ solo se ejecuta
            # cuando BT instancia este motor de verdad (al seleccionarlo), no al
            # arrancar el programa ni al registrar la clase.
            real_device_param = DEVICE_SELECTOR()
            saved_device = params.get("device")  # kwarg crudo: solo existe si venía de un proyecto/config guardado
            saved_value = saved_device.get("value") if isinstance(saved_device, dict) else None
            if saved_value in real_device_param.get("options", []):
                # El usuario ya había elegido un dispositivo válido antes: se respeta.
                real_device_param["value"] = saved_value
            # Si no había nada guardado, se queda con el valor por defecto que
            # acaba de detectar DEVICE_SELECTOR() (p.ej. 'cuda' si hay GPU).
            self.params["device"] = real_device_param
            self.device = real_device_param["value"]
            self.processor = None
            self.model = None
            self._fallback_ocr_instance = None

        def _load_model(self):
            import torch
            from transformers import AutoProcessor, AutoModelForImageTextToText
            dev = (self.params.get("device") or {}).get("value", "cpu")
            if dev in ("cuda", "gpu") and torch.cuda.is_available():
                dev = "cuda"
            else:
                dev = "cpu"
            if self.processor is not None and self.model is not None:
                if hasattr(self.model, "to"):
                    self.model.to(dev)
                self.device = dev
                return
            self.device = dev
            use_bf16 = self.params.get("use_bf16", {}).get("value", True)
            dtype = torch.bfloat16
            if not (torch.cuda.is_available() and getattr(torch.cuda, "is_bf16_supported", lambda: False)()):
                dtype = torch.float16
            if not use_bf16:
                dtype = torch.float16
            model_id = self._model_id
            self.processor = AutoProcessor.from_pretrained(model_id)
            self.model = AutoModelForImageTextToText.from_pretrained(
                model_id, torch_dtype=dtype, device_map=dev if dev == "cuda" else None
            )
            if dev == "cpu":
                self.model = self.model.to(dev)
            self.model.eval()

        def _run_one(self, pil_img: "Image.Image") -> str:
            import torch
            if pil_img.size[0] == 0 or pil_img.size[1] == 0:
                return ""
            tmp_path = None
            try:
                lang = (self.params.get("source_language") or {}).get("value", "Japanese") or "Japanese"
                prompt = _prompt_for_lang(lang)
                fd, tmp_path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                pil_img.save(tmp_path)
                img_ref = os.path.abspath(tmp_path)
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "url": img_ref},
                            {"type": "text", "text": prompt},
                        ],
                    }
                ]
                inputs = self.processor.apply_chat_template(
                    messages,
                    add_generation_prompt=True,
                    tokenize=True,
                    return_dict=True,
                    return_tensors="pt",
                )
                inputs.pop("token_type_ids", None)
                inputs = {k: (v.to(self.model.device) if hasattr(v, "to") else v) for k, v in inputs.items()}
                max_tokens = 512
                mt = self.params.get("max_new_tokens", {})
                if isinstance(mt, dict):
                    try:
                        max_tokens = max(64, min(2048, int(mt.get("value", 512))))
                    except (TypeError, ValueError):
                        pass
                with torch.inference_mode():
                    out = self.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
                input_len = inputs["input_ids"].shape[1]
                gen = out[0, input_len:]
                text = self.processor.decode(
                    gen,
                    skip_special_tokens=True,
                    clean_up_tokenization_spaces=False
                ).strip()

                clean_edge_quotes = self.params.get(
                    "clean_edge_quotes",
                    {}
                ).get(
                    "value",
                    True
                )

                if clean_edge_quotes:

                    while len(text) > 1 and text[0] in '\'"`´,“”‘’':
                        text = text[1:].strip()

                    while len(text) > 1 and text[-1] in '\'"`´,“”‘’':
                        text = text[:-1].strip()

                if len(text) > 120:

                    words = text.split()

                    if len(words) > 12:

                        first_chunk = " ".join(
                            words[:6]
                        )

                        repeated_count = text.count(
                            first_chunk
                        )

                        if repeated_count >= 3:
                            text = ""

                bad_callisto_messages = [
                    "je suis désolé",
                    "je suis desole",
                    "i am sorry",
                    "i'm sorry",
                    "lo siento",
                    "non posso",
                    "no puedo",
                    "i cannot",
                    "i can't",
                    "as a text assistant",
                    "as an ai",
                    "non riesco",
                    "non posso leggere",
                    "non posso tradurre",
                    "assistente testuale",
                    "non sono in grado",
                    "non posso aiutare",
                    "non posso interpretare",
                    "non posso vedere",
                ]

                text_lower = text.lower()

                if any(
                    msg in text_lower
                    for msg in bad_callisto_messages
                ):
                    text = "[OCR ERROR]"

                return text
 
            except Exception as e:
                self.logger.warning(f"VLM 2B OCR failed: {e}")
                return ""
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

        def _run_fallback_ocr(self, img: np.ndarray) -> str:

            fallback_name = self.params.get(
                "fallback_ocr",
                {}
            ).get(
                "value",
                "none"
            )

            if fallback_name == "none":
                return ""

            if fallback_name not in OCR.module_dict:
                return ""

            try:

                if self._fallback_ocr_instance is None:
                    fallback_cls = OCR.module_dict[fallback_name]
                    self._fallback_ocr_instance = fallback_cls()

                text = self._fallback_ocr_instance.run_ocr(
                    img
                )

                return str(text).strip() if text else ""

            except Exception as e:
                self.logger.warning(
                    f"Fallback OCR failed: {e}"
                )
                return ""

        def _ocr_blk_list(self, img: np.ndarray, blk_list: List[TextBlock], *args, **kwargs) -> None:
            im_h, im_w = img.shape[:2]
            pad = 0
            cp = self.params.get("crop_padding", {})
            if isinstance(cp, dict):
                try:
                    pad = max(0, min(24, int(cp.get("value", 0))))
                except (TypeError, ValueError):
                    pass
            for blk in blk_list:
                x1, y1, x2, y2 = blk.xyxy
                x1 = max(0, min(int(round(float(x1))), im_w - 1))
                y1 = max(0, min(int(round(float(y1))), im_h - 1))
                x2 = max(x1 + 1, min(int(round(float(x2))), im_w))
                y2 = max(y1 + 1, min(int(round(float(y2))), im_h))
                x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
                x2, y2 = min(im_w, x2 + pad), min(im_h, y2 + pad)
                if not (x1 < x2 and y1 < y2):
                    blk.text = [""]
                    continue
                crop = img[y1:y2, x1:x2]
                if crop.size == 0:
                    blk.text = [""]
                    continue
                pil_img = _cv2_to_pil_rgb(crop)
                text = self._run_one(pil_img)

                compact_text = str(text).replace(
                    " ",
                    ""
                ).replace(
                    "\n",
                    ""
                )

                suspicious_numeric = (
                    compact_text.isdigit()
                    and len(compact_text) <= 12
                )

                suspicious_coordinates = (
                    re.fullmatch(
                        r"\(\d{1,4},\d{1,4}\),\(\d{1,4},\d{1,4}\)",
                        compact_text
                    )
                    is not None
                )

                callisto_failed = (
                    not text
                    or text == "[OCR ERROR]"
                    or suspicious_numeric
                    or suspicious_coordinates
                )

                if callisto_failed:

                    fallback_text = self._run_fallback_ocr(
                        crop
                    )

                    if fallback_text:
                        text = fallback_text

                blk.text = [
                    text if text and text != "[OCR ERROR]" else ""
                ]

        def ocr_img(self, img: np.ndarray) -> str:
            if img.ndim == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
            return self._run_one(_cv2_to_pil_rgb(img))

        def updateParam(self, param_key: str, param_content):

            super().updateParam(param_key, param_content)

            preset = self.get_param_value("preset")

            if preset != "manual":

                if preset == "callisto_rapido":
                    self.set_param_value("crop_padding", 2)
                    self.set_param_value("max_new_tokens", 256)
                    self.set_param_value("use_bf16", True)

                elif preset == "callisto_equilibrado":
                    self.set_param_value("crop_padding", 4)
                    self.set_param_value("max_new_tokens", 512)
                    self.set_param_value("use_bf16", True)

                elif preset == "callisto_precision":
                    self.set_param_value("crop_padding", 6)
                    self.set_param_value("max_new_tokens", 768)
                    self.set_param_value("use_bf16", True)

                elif preset == "callisto_largo":
                    self.set_param_value("crop_padding", 8)
                    self.set_param_value("max_new_tokens", 1024)
                    self.set_param_value("use_bf16", True)

            if param_key == "device":
                self.device = (self.params.get("device") or {}).get("value", "cpu")
                if self.model is not None:
                    try:
                        self.model.to(self.device)
                    except Exception:
                        pass

    _VLM2BOCR._model_id = model_id
    return _VLM2BOCR


if _VLM2B_AVAILABLE:
    CallistoOCROCR = _make_vlm_2b_ocr(
        "callisto_ocr",
        "prithivMLmods/Callisto-OCR3-2B-Instruct",
        "Callisto-OCR3-2B – fast 2B OCR (HF); language-aware prompt.",
    )
    register_OCR("callisto_ocr")(CallistoOCROCR)

    Qwen2VLOCR2BOCR = _make_vlm_2b_ocr(
        "qwen2_vl_ocr_2b",
        "prithivMLmods/Qwen2-VL-OCR-2B-Instruct",
        "Qwen2-VL-OCR-2B – fast 2B OCR (HF); language-aware prompt.",
    )
    register_OCR("qwen2_vl_ocr_2b")(Qwen2VLOCR2BOCR)

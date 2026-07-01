from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from src.generator_base import ImageGenerator

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DiffusersGenerator(ImageGenerator):
    """Generate masked document edits with FLUX.1-Fill-dev via Diffusers."""

    base_model_id: str = "black-forest-labs/FLUX.1-Fill-dev"
    quantized_model_id: str = "diffusers/FLUX.1-Fill-dev-nf4"
    quantization_mode: str = "nf4"
    num_inference_steps: int = 30
    guidance_scale: float = 30.0
    device: str = "cuda"
    mask_margin: int = 8
    max_sequence_length: int = 512
    cache_dir: Path | None = None
    hf_token: str | None = None
    name: str = "diffusers"
    _pipeline: Any | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "DiffusersGenerator":
        cache_value = (
            os.environ.get("HF_MODEL_CACHE")
            or os.environ.get("KAGGLE_MODEL_CACHE")
            or os.environ.get("HF_HOME")
        )
        return cls(
            base_model_id=os.environ.get(
                "FLUX_FILL_MODEL_ID",
                "black-forest-labs/FLUX.1-Fill-dev",
            ),
            quantized_model_id=os.environ.get(
                "FLUX_FILL_QUANTIZED_MODEL_ID",
                "diffusers/FLUX.1-Fill-dev-nf4",
            ),
            quantization_mode=os.environ.get("FLUX_QUANTIZATION", "nf4").lower(),
            num_inference_steps=int(os.environ.get("FLUX_NUM_INFERENCE_STEPS", "30")),
            guidance_scale=float(os.environ.get("FLUX_GUIDANCE_SCALE", "30")),
            device=os.environ.get("DIFFUSERS_DEVICE", "cuda"),
            mask_margin=int(os.environ.get("FLUX_MASK_MARGIN", "8")),
            max_sequence_length=int(os.environ.get("FLUX_MAX_SEQUENCE_LENGTH", "512")),
            cache_dir=Path(cache_value).expanduser() if cache_value else None,
            hf_token=os.environ.get("HF_TOKEN"),
        )

    def generate(
        self,
        crop: Image.Image,
        prompt: str,
        bbox: list[int],
        seed: int | None = None,
    ) -> Image.Image:
        pipeline = self._get_pipeline()
        image = crop.convert("RGB")
        mask = self._build_mask(image.size, bbox)

        import torch

        generator = torch.Generator(device="cpu").manual_seed(0 if seed is None else seed)
        result = pipeline(
            prompt=prompt,
            image=image,
            mask_image=mask,
            height=image.height,
            width=image.width,
            guidance_scale=self.guidance_scale,
            num_inference_steps=self.num_inference_steps,
            max_sequence_length=self.max_sequence_length,
            generator=generator,
        ).images[0].convert("RGB")

        if result.size != image.size:
            raise RuntimeError(
                f"FLUX Fill returned {result.size}, expected the input size {image.size}"
            )
        return result

    def _build_mask(
        self,
        image_size: tuple[int, int],
        bbox: list[int],
    ) -> Image.Image:
        width, height = image_size
        if len(bbox) != 4:
            raise ValueError(f"Expected bbox [x1, y1, x2, y2], got {bbox!r}")

        x1, y1, x2, y2 = bbox
        x1 = max(0, min(width, x1 - self.mask_margin))
        y1 = max(0, min(height, y1 - self.mask_margin))
        x2 = max(0, min(width, x2 + self.mask_margin))
        y2 = max(0, min(height, y2 + self.mask_margin))
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f"Expanded bbox has no area: {bbox!r}")

        mask = Image.new("L", image_size, 0)
        ImageDraw.Draw(mask).rectangle((x1, y1, x2 - 1, y2 - 1), fill=255)
        return mask

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            self._pipeline = self._load_pipeline()
        return self._pipeline

    def _load_pipeline(self) -> Any:
        if self.quantization_mode != "nf4":
            raise ValueError(
                "FLUX_QUANTIZATION must be 'nf4'; this backend requires 4-bit NF4 weights"
            )
        if not self.hf_token:
            raise RuntimeError(
                "HF_TOKEN is required. Accept the FLUX.1-Fill-dev license on "
                "huggingface.co, then expose the token to the Kaggle environment."
            )

        import torch
        from diffusers import (
            FluxFillPipeline,
            FluxTransformer2DModel,
        )
        from transformers import T5EncoderModel

        dtype = torch.float16
        transformer = FluxTransformer2DModel.from_pretrained(
            self.quantized_model_id,
            subfolder="transformer",
            torch_dtype=dtype,
            cache_dir=self.cache_dir,
            token=self.hf_token,
        )
        text_encoder_2 = T5EncoderModel.from_pretrained(
            self.quantized_model_id,
            subfolder="text_encoder_2",
            torch_dtype=dtype,
            cache_dir=self.cache_dir,
            token=self.hf_token,
        )
        pipeline = FluxFillPipeline.from_pretrained(
            self.base_model_id,
            transformer=transformer,
            text_encoder_2=text_encoder_2,
            torch_dtype=dtype,
            cache_dir=self.cache_dir,
            token=self.hf_token,
        )

        if self.device.startswith("cuda"):
            # FLUX_NO_OFFLOAD=1 keeps the (NF4-quantised ~13 GB) weights resident
            # on the GPU instead of shuttling them from CPU RAM every step. This is
            # (a) much faster (no per-step host<->device copies) and (b) uses far
            # less *host* RAM -- essential when running one shard per GPU in
            # parallel, where two CPU-offloaded pipelines would exceed Kaggle's
            # ~30 GB RAM and OOM-kill the second shard. Falls back to offload if it
            # does not fit in VRAM.
            if os.environ.get("FLUX_NO_OFFLOAD") == "1":
                try:
                    pipeline.to(self.device)
                    logger.info("Weights resident on GPU (FLUX_NO_OFFLOAD=1)")
                except RuntimeError as exc:  # incl. torch CUDA OutOfMemoryError
                    logger.warning("No-offload load failed (%s); using CPU offload", exc)
                    pipeline.enable_model_cpu_offload()
            else:
                try:
                    pipeline.enable_model_cpu_offload()
                    logger.info("Enabled Diffusers model CPU offload")
                except (AttributeError, RuntimeError) as exc:
                    logger.warning("Model CPU offload failed (%s); using sequential offload", exc)
                    pipeline.enable_sequential_cpu_offload()
        else:
            pipeline.to(self.device)

        logger.info(
            "Loaded %s with pre-quantized NF4 components from %s on %s",
            self.base_model_id,
            self.quantized_model_id,
            self.device,
        )
        return pipeline

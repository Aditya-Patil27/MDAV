from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image


class ImageGenerator(ABC):
    """Backend-agnostic image editing generator interface."""

    name: str = "generator"

    @abstractmethod
    def generate(
        self,
        crop: Image.Image,
        prompt: str,
        bbox: list[int],
        seed: int | None = None,
    ) -> Image.Image:
        """Edit the supplied crop and return the modified image."""


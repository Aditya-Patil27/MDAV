# Optional Hugging Face Classifier Fallback

The preferred AIForge backend is the local segmentation checkpoint:

```text
models/best_diffusion.pth
MDAV_DIFFUSION_WEIGHTS=/app/models/best_diffusion.pth
```

`backend/app/services/diffusion_service.py` can also load a real-versus-AI
image classifier, but only when `MDAV_DIFFUSION_MODEL` is explicitly set and
the segmentation checkpoint cannot load. There is no default Hub model and no
network download during normal backend startup.

For an offline classifier fallback, place a complete Transformers model folder
here and configure:

```text
MDAV_DIFFUSION_MODEL=../models/diffusion
```

The directory normally includes:

```text
models/diffusion/
|-- model.safetensors
|-- config.json
`-- preprocessor_config.json
```

Potential source models include
[Ateeqq/ai-vs-human-image-detector](https://huggingface.co/Ateeqq/ai-vs-human-image-detector/tree/main)
(Apache-2.0) and
[Organika/sdxl-detector](https://huggingface.co/Organika/sdxl-detector/tree/main)
(CC-BY-NC; non-commercial). Review each model's license before use. The
selected model's `id2label` must identify an AI, fake, generated, synthetic,
GAN, or diffusion class.

All files except this README are git-ignored. If the segmentation checkpoint,
fallback files, dependencies, or compatible labels are unavailable, the branch
emits vacuous belief and verification continues.

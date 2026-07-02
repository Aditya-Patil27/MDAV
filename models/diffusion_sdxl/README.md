# models/diffusion_sdxl/  —  alternative diffusion-branch model (SDXL-specialised)

The [Organika/sdxl-detector](https://huggingface.co/Organika/sdxl-detector) model
(Swin, trained on SDXL image pairs; labels `artificial`/`human`). A diffusion-
specialised alternative to the default `models/diffusion/` (ai-vs-human) model.

**License: CC-BY-NC (non-commercial).** Fine for research/demo/evaluation; do
**not** use in a commercial deployment. The default Apache-2.0 model stays active
unless you deliberately switch.

## To use it instead of the default

Point the branch at this folder (no code change):
```
MDAV_DIFFUSION_MODEL=/app/models/diffusion_sdxl     # Docker
MDAV_DIFFUSION_MODEL=./models/diffusion_sdxl        # local
```

Weights are git-ignored (only this README is tracked). Contains
`model.safetensors` + `config.json` + `preprocessor_config.json`.

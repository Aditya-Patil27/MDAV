# models/diffusion/  —  AI-generated forgery branch weights

Drop the pretrained detector's **3 files** here (this exact folder). The backend
loads them via `MDAV_DIFFUSION_MODEL=/app/models/diffusion` (Docker) or
`./models/diffusion` (local) — see `backend/app/services/diffusion_service.py`.

Put these together in this directory:

```
models/diffusion/
├── model.safetensors
├── config.json
└── preprocessor_config.json
```

## Where to get them

**Default — Apache-2.0 (commercial-safe):** [Ateeqq/ai-vs-human-image-detector](https://huggingface.co/Ateeqq/ai-vs-human-image-detector/tree/main)
- https://huggingface.co/Ateeqq/ai-vs-human-image-detector/resolve/main/model.safetensors
- https://huggingface.co/Ateeqq/ai-vs-human-image-detector/resolve/main/config.json
- https://huggingface.co/Ateeqq/ai-vs-human-image-detector/resolve/main/preprocessor_config.json

**Alt — diffusion/SDXL-specialised (CC-BY-NC, non-commercial):** [Organika/sdxl-detector](https://huggingface.co/Organika/sdxl-detector/tree/main) (same 3 filenames).

## Notes

- All **3 files** are required — `transformers` needs `config.json` to know the
  architecture; the weights alone won't load.
- The files are git-ignored (only this README is tracked) — never commit the 372 MB weights.
- If this folder is empty/absent, the branch degrades gracefully to a **vacuous**
  belief (contributes nothing) and the pipeline still runs.
- To swap models later, just replace the files here — no code change.

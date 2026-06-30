from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

BASE_MODEL_ID = "black-forest-labs/FLUX.1-Fill-dev"
QUANTIZED_MODEL_ID = "diffusers/FLUX.1-Fill-dev-nf4"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("setup_kaggle")


def base_dir() -> Path:
    return Path(os.environ.get("BASE_DIR", Path.cwd())).expanduser().resolve()


def model_cache_dir() -> Path:
    configured = os.environ.get("KAGGLE_MODEL_CACHE") or os.environ.get("HF_MODEL_CACHE")
    if configured:
        return Path(configured).expanduser().resolve()
    return (base_dir() / ".cache" / "huggingface").resolve()


def install_tesseract() -> None:
    """Install Tesseract with English and Korean language data on Kaggle."""
    if os.name == "nt":
        raise RuntimeError(
            "setup_kaggle.py requires a Debian-based Kaggle runtime to install "
            "tesseract-ocr-kor; it cannot install that package on Windows."
        )
    subprocess.run(["apt-get", "update", "-qq"], check=True)
    subprocess.run(
        [
            "apt-get",
            "install",
            "-y",
            "-qq",
            "tesseract-ocr",
            "tesseract-ocr-eng",
            "tesseract-ocr-kor",
        ],
        check=True,
    )


def install_requirements() -> None:
    requirements = base_dir() / "requirements.txt"
    if not requirements.exists():
        raise FileNotFoundError(f"requirements.txt not found under BASE_DIR: {requirements}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
        check=True,
    )


def require_hf_token() -> str:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set. Accept the FLUX.1-Fill-dev license on "
            "huggingface.co, add HF_TOKEN as a Kaggle secret, and expose it "
            "as an environment variable before running setup_kaggle.py."
        )
    return token


def model_snapshot_specs() -> list[tuple[str, list[str] | None]]:
    """Return disk-bounded snapshots required by the NF4 pipeline."""
    return [
        (QUANTIZED_MODEL_ID, None),
        (
            BASE_MODEL_ID,
            [
                "model_index.json",
                "scheduler/**",
                "text_encoder/**",
                "tokenizer/**",
                "tokenizer_2/**",
                "vae/**",
            ],
        ),
    ]


def cache_model(token: str, cache_dir: Path) -> list[Path]:
    from huggingface_hub import login, snapshot_download
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError

    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache_dir)
    os.environ["HF_MODEL_CACHE"] = str(cache_dir)
    login(token=token, add_to_git_credential=False)
    snapshot_paths: list[Path] = []
    try:
        for repo_id, allow_patterns in model_snapshot_specs():
            logger.info("Caching %s under %s", repo_id, cache_dir)
            kwargs = {
                "repo_id": repo_id,
                "cache_dir": cache_dir,
                "token": token,
            }
            if allow_patterns is not None:
                kwargs["allow_patterns"] = allow_patterns
            snapshot_paths.append(Path(snapshot_download(**kwargs)))
    except (GatedRepoError, HfHubHTTPError) as exc:
        raise RuntimeError(
            "Hugging Face rejected the FLUX.1-Fill-dev download. Confirm that "
            "the token is valid and its account has accepted the model license."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "Model caching failed. Ensure the Kaggle working disk has at least "
            "16 GiB free and remove any partial cache from an earlier full-model download."
        ) from exc
    return snapshot_paths


def print_gpu_summary() -> None:
    import torch

    if not torch.cuda.is_available():
        logger.warning("CUDA is unavailable; select a Kaggle T4 or P100 accelerator.")
        return
    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        vram_gib = properties.total_memory / (1024**3)
        logger.info("GPU %d: %s (%.1f GiB VRAM)", index, properties.name, vram_gib)
        if vram_gib < 14:
            logger.warning("GPU %d has less than the recommended 14 GiB VRAM.", index)


def main() -> None:
    install_tesseract()
    install_requirements()
    token = require_hf_token()
    snapshot_paths = cache_model(token, model_cache_dir())
    print_gpu_summary()
    logger.info("Kaggle setup complete. Cached model snapshots: %s", snapshot_paths)
    logger.info("Run generation with: python main.py --output-dir <shard-output>")


if __name__ == "__main__":
    main()

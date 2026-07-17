FROM python:3.10-slim

WORKDIR /app

# System libs: libjpeg (jpegio build) + OpenCV/Ultralytics runtime deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libjpeg-dev zlib1g-dev libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-docker.txt ./
# Docker Desktop runs the backend without NVIDIA passthrough. Install the
# official CPU builds first so the general requirements do not pull several
# gigabytes of CUDA runtime wheels into this image.
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.4.0 torchvision==0.19.0
RUN pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        --constraint requirements-docker.txt \
        -r requirements.txt

COPY . .
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

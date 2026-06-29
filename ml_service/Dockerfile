FROM python:3.10-slim

WORKDIR /app

# libjpeg is required to build jpegio; libgl/glib for OpenCV.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libjpeg-dev zlib1g-dev libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["uvicorn", "inference:app", "--host", "0.0.0.0", "--port", "8001"]

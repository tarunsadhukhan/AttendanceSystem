FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir git+https://github.com/ageitgey/face_recognition_models

COPY . .

EXPOSE 5051
CMD ["gunicorn", "--bind", "0.0.0.0:5051", "--timeout", "120", "app:app"]

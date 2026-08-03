FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Jingles folder will be mounted as a volume
RUN mkdir -p jingles

CMD ["python", "bot.py"]

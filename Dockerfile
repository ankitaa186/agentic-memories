FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Install system build tools for native Python deps (e.g., chroma-hnswlib)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
	&& pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY tests ./tests
COPY docker-entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Expose app port and debug port (5679 by default, configurable)
EXPOSE 8080
EXPOSE 5679

CMD ["./docker-entrypoint.sh"]

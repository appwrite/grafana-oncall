FROM python:3.15.0-alpine3.23@sha256:d64bc17e0dff27c5c4a31f616450d032aa73d6325855127ce3a305bf1384c8d5

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -U pip
RUN python3 -m pip install --no-cache-dir -r requirements.txt && \
    python3 -m pip uninstall -y pip && \
    rm -rf /usr/local/lib/python3.14/ensurepip

COPY . .

# Create data directory and generate session ID
RUN mkdir -p /app/data && \
    python3 -c "import uuid; open('/app/data/.session', 'w').write(str(uuid.uuid4()))"

# Set session file location
ENV SESSION_FILE=/app/data/.session

CMD ["python3", "main.py"]

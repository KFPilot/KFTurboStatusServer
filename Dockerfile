FROM python:3.11-slim

# Don't create .pyc files inside the container.
ENV PYTHONDONTWRITEBYTECODE=1
# Flush logs immediately to stdout/stderr.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE /app/
COPY *.py /app/
COPY img /app/img

RUN pip install --no-cache-dir .

CMD ["python", "KFTurboServerStatus.py"]

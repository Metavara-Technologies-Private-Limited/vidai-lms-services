# Backend Dockerfile (Django)

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1

# Prevent python output buffering
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies 
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

# Install python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


COPY . .


RUN python manage.py collectstatic --noinput || true


# ✅ Ensure media and log directories exist inside the container.
# The media/ directory will be overridden by the Docker volume mount,
# so uploaded files (profile photos, documents) are persisted on the host.
RUN mkdir -p /app/media/user_profiles \
    && mkdir -p /app/media/lead_documents \
    && mkdir -p /app/media/template_mail_documents \
    && mkdir -p /app/restapi/log \
    && touch /app/restapi/log/api.log

# Declare media as a mountable volume.
# When docker-compose mounts a volume here, files survive container rebuilds.
VOLUME ["/app/media"]

EXPOSE 8000


CMD ["gunicorn", "lms_main.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]

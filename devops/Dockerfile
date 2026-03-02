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
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .

# Install python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


COPY . .


RUN python manage.py collectstatic --noinput || true


# log directory and file required by app
RUN mkdir -p /app/restapi/log \
    && touch /app/restapi/log/api.log

EXPOSE 8000


CMD ["gunicorn", "lms_main.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]

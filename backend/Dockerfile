FROM python:3.13.5
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir
RUN apt-get update && apt-get install -y postgresql-client
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "foodgram_backend.wsgi"]

FROM python:3.10-slim

WORKDIR /app

COPY ./app /app/app
COPY requirements.txt .
COPY ./config /app/config 

RUN apt-get update && apt-get install -y ffmpeg
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps

ENV PYTHONPATH="${PYTHONPATH}:/app"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
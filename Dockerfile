FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y build-essential libmariadb-dev pkg-config

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8081"]

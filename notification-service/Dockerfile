FROM python:3.11-slim
WORKDIR /app

# Copy and install dependencies first (better caching)
COPY notification-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code
COPY shared ./shared

# Copy notification service code (changes most frequently, so last)
COPY notification-service/app ./app

# Run the notification listener (event consumer)
CMD ["python", "-u", "-m", "app.listeners"]

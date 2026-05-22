FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8900

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8900"]

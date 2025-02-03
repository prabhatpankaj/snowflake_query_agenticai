FROM python:3.13.1-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Ensure Python can find the 'agenticai' module
ENV PYTHONPATH="/app"

# Expose the application port
EXPOSE 8000

# Start the application with Waitress
CMD ["python", "-m", "waitress", "--host=0.0.0.0", "--port=8000", "app:app"]

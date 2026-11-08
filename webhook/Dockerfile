# Use lightweight Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install Flask
RUN pip install --no-cache-dir flask

# Copy application
COPY app.py .

# Expose Flask port
EXPOSE 5001

# Start Flask application
CMD ["python", "app.py"]
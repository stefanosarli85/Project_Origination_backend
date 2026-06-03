# Use official Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Fix missing tmp directory
RUN mkdir -p /tmp && chmod 1777 /tmp

# Copy dependency file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port Uvicorn runs on
EXPOSE 1701

# Run the FastAPI app
CMD ["uvicorn", "main:apps", "--host", "0.0.0.0", "--port", "1701"]
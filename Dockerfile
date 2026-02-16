# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Expose port (Optional: if you run FastMCP as an SSE server, default is usually dynamic or 8000)
# ENV PORT=8000
# EXPOSE 8000

# Define environment variables with defaults (can be overridden at runtime)
# OPENAI_API_KEY is optional/secret
ENV MODAL_TOKEN_ID=""
ENV MODAL_TOKEN_SECRET=""

# Command to run the application
# We use standard IO mode for MCP by default, but this can be changed to an SSE server
CMD ["python", "gateway.py"]

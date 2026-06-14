# Base image
FROM python:3.10-slim

# Install Node.js for MERN backend
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies for YOLOv8
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies (if package.json exists)
RUN if [ -f package.json ] ; then npm install --no-audit --no-fund ; fi

# Command to run both Node.js and Python backend
CMD ["sh", "-c", "node server.js & python backend/app.py"]

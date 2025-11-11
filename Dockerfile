# Use Playwright's official Python image (includes Python, browsers, and dependencies)
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# Set working directory inside container
WORKDIR /app

# Copy dependency file first (for better build caching)
COPY requirements.txt .

# Upgrade pip & install dependencies efficiently
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project files
COPY . .

# Install Playwright browsers (safeguard in case they're missing)
RUN playwright install --with-deps chromium

# Set default command to run your scraper
CMD ["python", "amazon_reviews_scraper.py"]

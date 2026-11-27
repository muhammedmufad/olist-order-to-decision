# Start from a small official Python image with the same version as the project.
FROM python:3.12-slim

WORKDIR /project

# Install only what the API needs. Copied first, so Docker can reuse this layer
# when only the code changes.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy the service, the trained model and the tests.
COPY app/ app/
COPY models/ models/
COPY tests/ tests/

EXPOSE 8000

# 0.0.0.0 = accept connections from outside the container, not only from inside it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
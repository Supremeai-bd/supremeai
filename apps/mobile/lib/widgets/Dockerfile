# ---- Builder Stage ----
# Use a full Python image to build dependencies, which may require build tools.
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy only the dependency definition files
COPY poetry.lock pyproject.toml ./

# Configure Poetry to create the virtual environment inside the project directory
RUN poetry config virtualenvs.in-project true

# Install production dependencies only, without creating a virtual environment wrapper
# --no-cache-dir is crucial for reducing image size
RUN poetry install --no-dev --no-interaction --no-ansi


# ---- Final Stage ----
# Use a distroless base image for a minimal and secure final image.
# It only contains the Python interpreter and its direct dependencies.
FROM gcr.io/distroless/python3-debian11

# Set the working directory
WORKDIR /app

# Set environment variables for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production

# Copy the virtual environment with installed dependencies from the builder stage
COPY --from=builder /app/.venv ./.venv

# Set the PATH to use the virtual environment's Python
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application source code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application using the virtual environment's uvicorn
CMD ["uvicorn", "core.app:app", "--host", "0.0.0.0", "--port", "8000"]
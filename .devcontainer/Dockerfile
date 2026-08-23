FROM mcr.microsoft.com/devcontainers/python:3.11

# Install nodejs for frontend dev if needed
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g npm@latest

# Install redis-tools and postgresql-client for DB debugging
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends redis-tools postgresql-client

# Install global Python tools
RUN pip install --upgrade pip
RUN pip install poetry ruff pytest

# [Optional] Uncomment this section to install additional OS packages.
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>

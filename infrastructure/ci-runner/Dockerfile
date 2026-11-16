FROM ubuntu:24.04

LABEL maintainer="SupremeAI Team"
LABEL description="SupremeAI Self-Hosted Linux CI Runner on Kiri"

ENV DEBIAN_FRONTEND=noninteractive
ENV POWERSHELL_VERSION=7.4.6

# 1. Switch to high-speed mirror to avoid local ISP proxy drops, install base utilities, git, python, and runtime libraries
RUN sed -i 's|archive.ubuntu.com|mirror.sg.gs|g; s|security.ubuntu.com|mirror.sg.gs|g' /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    tar \
    git \
    jq \
    sudo \
    iputils-ping \
    libicu-dev \
    libssl-dev \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    python-is-python3 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# 2. Install jscpd globally for fast duplicate detection
RUN npm install -g jscpd@5.4.3 && npm cache clean --force

# 3. Install PowerShell Core (pwsh) and symlink to both pwsh and powershell
RUN mkdir -p /opt/microsoft/powershell/7 \
    && curl -fsSL "https://github.com/PowerShell/PowerShell/releases/download/v${POWERSHELL_VERSION}/powershell-${POWERSHELL_VERSION}-linux-x64.tar.gz" \
       -o /tmp/powershell.tar.gz \
    && tar -zxf /tmp/powershell.tar.gz -C /opt/microsoft/powershell/7 \
    && chmod +x /opt/microsoft/powershell/7/pwsh \
    && ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/pwsh \
    && ln -s /opt/microsoft/powershell/7/pwsh /usr/bin/powershell \
    && rm -f /tmp/powershell.tar.gz

# 4. Create runner user with passwordless sudo
RUN useradd -m -s /bin/bash runner \
    && echo "runner ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/runner \
    && chmod 0440 /etc/sudoers.d/runner

# 5. Download and extract GitHub Actions Runner (v2.338.2)
ENV RUNNER_VERSION=2.338.2
USER runner
WORKDIR /home/runner/actions-runner

RUN curl -fsSL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
    -o runner.tar.gz \
    && tar -zxf runner.tar.gz \
    && rm -f runner.tar.gz

USER root
COPY entrypoint.sh /home/runner/entrypoint.sh
RUN chmod +x /home/runner/entrypoint.sh \
    && chown -R runner:runner /home/runner

USER runner
WORKDIR /home/runner/actions-runner

ENTRYPOINT ["/home/runner/entrypoint.sh"]

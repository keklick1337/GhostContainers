# Debian Trixie (testing) with X11 and development tools
FROM debian:trixie

# Update and install base packages
RUN apt-get update && apt-get install -y \
    sudo \
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    procps \
    net-tools \
    iputils-ping \
    ca-certificates \
    gnupg \
    lsb-release \
    x11-apps \
    xauth \
    firefox-esr \
    && rm -rf /var/lib/apt/lists/*

# Create user with sudo
ARG USER_NAME=user
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid $USER_GID $USER_NAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USER_NAME \
    && echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Working directory
USER $USER_NAME
WORKDIR /home/$USER_NAME

# Environment variables for X11
ENV DISPLAY=:0
ENV XAUTHORITY=/tmp/.Xauthority

CMD ["/bin/bash"]

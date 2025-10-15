# Ubuntu Desktop - minimal environment
FROM ubuntu:24.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Update and install packages
RUN apt-get update && apt-get install -y \
    sudo \
    x11-apps \
    xauth \
    dbus-x11 \
    firefox \
    xterm \
    nano \
    vim \
    wget \
    curl \
    git \
    htop \
    net-tools \
    iputils-ping \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create user
ARG USER_NAME=user
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid $USER_GID $USER_NAME && \
    useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USER_NAME && \
    echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Configure dbus for GUI applications
RUN mkdir -p /var/run/dbus

USER $USER_NAME
WORKDIR /home/$USER_NAME

ENV DISPLAY=:0
ENV XAUTHORITY=/tmp/.Xauthority

CMD ["/bin/bash"]

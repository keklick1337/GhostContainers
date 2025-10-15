# Alpine Linux 3.22 - Lightweight container with X11 support
FROM alpine:3.22

# Install base packages
RUN apk add --no-cache \
    sudo \
    bash \
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    ca-certificates \
    xauth \
    xorg-server \
    python3 \
    py3-pip \
    build-base

# Create user with sudo
ARG USER_NAME=user
ARG USER_UID=1000
ARG USER_GID=1000

RUN addgroup -g $USER_GID $USER_NAME \
    && adduser -D -u $USER_UID -G $USER_NAME $USER_NAME \
    && echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER $USER_NAME
WORKDIR /home/$USER_NAME

ENV DISPLAY=:0
ENV XAUTHORITY=/tmp/.Xauthority

CMD ["/bin/bash"]

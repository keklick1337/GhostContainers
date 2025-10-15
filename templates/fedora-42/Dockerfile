# Fedora 42 with modern development tools
FROM fedora:42

# Install packages
RUN dnf update -y && dnf install -y \
    sudo \
    git \
    vim \
    nano \
    htop \
    procps-ng \
    net-tools \
    iputils \
    firefox \
    chromium \
    python3 \
    python3-pip \
    gcc \
    g++ \
    make \
    xorg-x11-apps \
    xauth \
    && dnf clean all

# Create user
ARG USER_NAME=user
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid $USER_GID $USER_NAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USER_NAME \
    && echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER $USER_NAME
WORKDIR /home/$USER_NAME

ENV DISPLAY=:0
ENV XAUTHORITY=/tmp/.Xauthority

CMD ["/bin/bash"]

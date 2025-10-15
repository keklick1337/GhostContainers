FROM alpine:latest

# Install build dependencies and runtime dependencies
RUN apk update && \
    apk add --no-cache \
        tor \
        supervisor \
        git \
        go \
        make \
        && rm -rf /var/cache/apk/*

# Build lyrebird (obfs4proxy) from source
WORKDIR /tmp
RUN git clone https://gitlab.torproject.org/tpo/anti-censorship/pluggable-transports/lyrebird.git && \
    cd lyrebird && \
    make build && \
    cp lyrebird /usr/bin/obfs4proxy && \
    chmod +x /usr/bin/obfs4proxy && \
    cd / && \
    rm -rf /tmp/lyrebird

# Create directories and set permissions (tor user already exists)
RUN mkdir -p /var/lib/tor /var/log/tor /etc/tor && \
    chown -R tor:tor /var/lib/tor /var/log/tor

# Copy Tor configuration
COPY torrc /etc/tor/torrc

# Create supervisor configuration
RUN mkdir -p /etc/supervisor.d

# Copy supervisor configuration as inline heredoc
RUN cat > /etc/supervisord.conf << 'SUPERVISOR_EOF'
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
childlogdir=/var/log/supervisor

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock

[unix_http_server]
file=/var/run/supervisor.sock
chmod=0700

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:tor]
command=/usr/bin/tor -f /etc/tor/torrc
user=tor
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/tor_error.log
stdout_logfile=/var/log/supervisor/tor_stdout.log
environment=HOME="/var/lib/tor"
SUPERVISOR_EOF

# Set permissions
RUN chown -R tor:tor /etc/tor && \
    chmod 644 /etc/tor/torrc

# Create log directory
RUN mkdir -p /var/log/supervisor && \
    chown -R tor:tor /var/log/supervisor

EXPOSE 9050 9051

# Use supervisor to manage Tor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
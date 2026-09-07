#!/bin/sh
# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
#
# Runs from /docker-entrypoint.d/ before nginx starts. Enables the HTTPS
# listener only when a certificate pair is mounted at /etc/nginx/certs/,
# so one image serves both plain-HTTP and TLS deployments.
set -e

mkdir -p /etc/nginx/tls
if [ -f /etc/nginx/certs/fullchain.pem ] && [ -f /etc/nginx/certs/privkey.pem ]; then
    cp /etc/nginx/tls-server.conf /etc/nginx/tls/server.conf
    echo "40-tls.sh: certificates found, HTTPS enabled on :443"
else
    rm -f /etc/nginx/tls/server.conf
    echo "40-tls.sh: no certificates at /etc/nginx/certs/, serving HTTP only"
fi

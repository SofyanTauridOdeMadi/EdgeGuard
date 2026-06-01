#!/bin/bash
# Jalankan SEKALI di VPS untuk generate SSL certificate self-signed
# bash ssl_setup.sh

CERT_DIR="$(dirname "$0")/dashboard/ssl"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 3650 \
  -newkey rsa:2048 \
  -keyout "$CERT_DIR/key.pem" \
  -out    "$CERT_DIR/cert.pem" \
  -subj   "/C=ID/O=EdgeGuard/CN=EdgeGuard" \
  2>/dev/null

echo "✓ SSL certificate dibuat (berlaku 10 tahun)"
echo "  cert : $CERT_DIR/cert.pem"
echo "  key  : $CERT_DIR/key.pem"
echo ""

#!/bin/sh
set -e

# Generate htpasswd file if AUTH_USERNAME and AUTH_PASSWORD are set
if [ -n "$AUTH_USERNAME" ] && [ -n "$AUTH_PASSWORD" ]; then
    echo "Setting up basic auth for user: $AUTH_USERNAME"
    htpasswd -bc /etc/nginx/.htpasswd "$AUTH_USERNAME" "$AUTH_PASSWORD"
else
    echo "No AUTH_USERNAME/AUTH_PASSWORD set, basic auth disabled"
    rm -f /etc/nginx/.htpasswd
fi

exec "$@"

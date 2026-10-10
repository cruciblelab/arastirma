#!/bin/sh
# Android istemci kodunu (JVM üzerinde) gerçek Linux sunucusuna karşı dener.
#   sh kopru/linux/tests/android_canli_test.sh
set -eu
cd "$(dirname "$0")"
python3 canli_sunucu.py > /tmp/kopru-canli.out 2> /tmp/kopru-canli.log &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT
for _ in $(seq 50); do [ -s /tmp/kopru-canli.out ] && break; sleep 0.2; done
read -r PORT SHA DIR < /tmp/kopru-canli.out
cd ../../android
KOPRU_TEST_PORT=$PORT KOPRU_TEST_PASSWORD=test-sifre KOPRU_TEST_RECEIVE_DIR=$DIR KOPRU_TEST_SEND_SHA=$SHA \
    ./gradlew --quiet testReleaseUnitTest --tests lab.crucible.kopru.LiveServerTest --rerun-tasks
echo "Canlı test geçti (sunucu günlüğü: /tmp/kopru-canli.log)"

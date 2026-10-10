#!/bin/sh
# Android istemci kodunu (JVM üzerinde) gerçek Linux sunucusuna karşı dener.
#   sh talk-to/linux/tests/android_canli_test.sh
set -eu
cd "$(dirname "$0")"
python3 canli_sunucu.py > /tmp/talkto-canli.out 2> /tmp/talkto-canli.log &
PID=$!
trap 'kill $PID 2>/dev/null' EXIT
for _ in $(seq 50); do [ -s /tmp/talkto-canli.out ] && break; sleep 0.2; done
read -r PORT SHA DIR < /tmp/talkto-canli.out
cd ../../android
TALKTO_TEST_PORT=$PORT TALKTO_TEST_PASSWORD=test-sifre TALKTO_TEST_RECEIVE_DIR=$DIR TALKTO_TEST_SEND_SHA=$SHA \
    ./gradlew --quiet testReleaseUnitTest --tests 'lab.crucible.talktolinux.LiveServerTest' --rerun-tasks
echo "Canlı test geçti (sunucu günlüğü: /tmp/talkto-canli.log)"

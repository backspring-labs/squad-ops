#!/usr/bin/env bash
# #2560: start the integration job's three services (postgres, redis, rabbitmq), pulling each image
# from Google's mirror with retries and falling back to Docker Hub's anonymous pull.
#
# The job's `services:` block pulled from the mirror once and could not fall back: on 2026-10-20 the
# mirror's request quota (`toomanyrequests`, shared by GitHub's runners) failed the required job with
# no test run. #2201 had moved off Docker Hub for its own anonymous limit (the 2.3 plan's D7), so
# each registry is the other's fallback, with no account and no secret.
#
# The containers are the ones the block declared: the same images, environment, published ports and
# health checks. The script waits until all three report healthy and exits non-zero when one can't
# be pulled or doesn't become healthy, naming it.
#
# Env (each defaulted to what CI uses; a local check overrides them to stay off a deploy's ports):
#   MIRROR          the mirror's library prefix   (mirror.gcr.io/library)
#   HUB             the fallback's library prefix (docker.io/library)
#   NAME_PREFIX     the container-name prefix     (ci-)
#   PG_PORT, REDIS_PORT, AMQP_PORT, AMQP_UI_PORT  (5432, 6379, 5672, 15672)
#   HEALTH_TIMEOUT  seconds to wait for healthy   (300)
set -euo pipefail

MIRROR="${MIRROR:-mirror.gcr.io/library}"
HUB="${HUB:-docker.io/library}"
NAME_PREFIX="${NAME_PREFIX:-ci-}"
PG_PORT="${PG_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"
AMQP_PORT="${AMQP_PORT:-5672}"
AMQP_UI_PORT="${AMQP_UI_PORT:-15672}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-300}"

# The image reference that pulled: the mirror's, else Docker Hub's, three tries each.
pull() {
    local image="$1" registry attempt
    for registry in "$MIRROR" "$HUB"; do
        for attempt in 1 2 3; do
            if docker pull -q "$registry/$image" >&2; then
                echo "$registry/$image"
                return 0
            fi
            echo "pull $registry/$image failed (try $attempt of 3)" >&2
            sleep $((attempt * 10))
        done
    done
    echo "could not pull $image from $MIRROR or $HUB" >&2
    return 1
}

postgres=$(pull postgres:15)
redis=$(pull redis:7-alpine)
rabbitmq=$(pull rabbitmq:3.12-management)

# The test role and its database are provisioned by ensure_test_database.sh, not by this image
# (#1180): POSTGRES_DB is the deployment database, owned by the superuser squadops.
docker run -d --name "${NAME_PREFIX}postgres" \
    -e POSTGRES_USER=squadops -e POSTGRES_PASSWORD=squadops-dev -e POSTGRES_DB=squadops \
    -p "$PG_PORT:5432" \
    --health-cmd "pg_isready -U squadops" \
    --health-interval 10s --health-timeout 5s --health-retries 10 \
    "$postgres" >/dev/null
docker run -d --name "${NAME_PREFIX}redis" \
    -p "$REDIS_PORT:6379" \
    --health-cmd "redis-cli ping" \
    --health-interval 10s --health-timeout 5s --health-retries 10 \
    "$redis" >/dev/null
# The broker must CREATE the user the tests authenticate as: the stock image ships `guest` alone.
docker run -d --name "${NAME_PREFIX}rabbitmq" \
    -e RABBITMQ_DEFAULT_USER=squadops -e RABBITMQ_DEFAULT_PASS=squadops-dev \
    -p "$AMQP_PORT:5672" -p "$AMQP_UI_PORT:15672" \
    --health-cmd "rabbitmq-diagnostics -q ping" \
    --health-interval 10s --health-timeout 10s --health-retries 15 \
    "$rabbitmq" >/dev/null

deadline=$((SECONDS + HEALTH_TIMEOUT))
for service in postgres redis rabbitmq; do
    name="${NAME_PREFIX}${service}"
    until [ "$(docker inspect --format '{{.State.Health.Status}}' "$name")" = "healthy" ]; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            echo "$name did not become healthy within ${HEALTH_TIMEOUT}s" >&2
            docker logs --tail 20 "$name" >&2 || true
            exit 1
        fi
        sleep 3
    done
    echo "$name healthy ($(docker inspect --format '{{.Config.Image}}' "$name"))"
done

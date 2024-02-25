#!/bin/bash

set -e

cd "${0%/*}"

image="gcr.io/semi-automated-benchmarking/load-test-importer:$GIT_HASH"
docker build --platform="linux/amd64" -t "$image" .
docker push "$image"

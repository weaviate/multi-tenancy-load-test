#!/bin/bash

cd "${0%/*}"

kubectl delete pod schema-resetter || true
envsubst < manifests/reset-schema-pod.yaml | kubectl apply -f -


#!/bin/bash

cd "${0%/*}"

envsubst < manifests/import-job.yaml | kubectl apply -f -


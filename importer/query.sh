#!/bin/bash

cd "${0%/*}"

for rep in 5 10 15 20 25 30 35 40 45 50 55 60 55 45 40 35 30 25 20 15 10 5 0; do
  echo "Scaling to $rep replicas"
  QUERY_REPLICAS=$rep envsubst < manifests/querying-deployment.yaml | kubectl apply -f -
  sleep 60;
done



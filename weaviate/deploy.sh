#!/bin/bash

cd "${0%/*}"

helm repo add weaviate https://weaviate.github.io/weaviate-helm | true
kubectl create ns "$K8S_NAMESPACE" | true

helm upgrade \
  --install weaviate-load-test weaviate/weaviate --version 16.8.1 \
  --values values.yaml \
  --namespace "$K8S_NAMESPACE" \
  --set "image.tag=$WEAVIATE_VERSION" \
  --set replicas="$WEAVIATE_PODS"



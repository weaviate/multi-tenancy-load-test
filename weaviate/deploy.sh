#!/bin/bash

cd "${0%/*}"

helm repo add weaviate https://weaviate.github.io/weaviate-helm | true
kubectl create ns "$K8S_NAMESPACE" | true

helm upgrade \
  --install weaviate-load-test weaviate/weaviate \
  --values values.yaml \
  --namespace "$K8S_NAMESPACE" \
  --set "image.tag=$WEAVIATE_VERSION" \
  --set replicas=3



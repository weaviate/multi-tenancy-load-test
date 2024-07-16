#!/bin/bash

cd "${0%/*}"

rm -rf "/tmp/weaviate-helm"
git clone https://github.com/weaviate/weaviate-helm.git "/tmp/weaviate-helm" 
helm package -d /tmp/weaviate-helm /tmp/weaviate-helm/weaviate 

kubectl create ns "$K8S_NAMESPACE" | true

if [[ -n "$ACCESS_KEY" && -n "$SECRET_KEY" && "$ACCESS_KEY" != "" && "$SECRET_KEY" != "" ]]; then
  offload_secrets="--set offload.s3.secrets.AWS_ACCESS_KEY_ID=${ACCESS_KEY} --set offload.s3.secrets.AWS_SECRET_ACCESS_KEY=${SECRET_KEY}"
else
  offload_secrets=""
fi

helm upgrade \
  --install weaviate-load-test /tmp/weaviate-helm/weaviate-*.tgz \
  --values values.yaml \
  --namespace "$K8S_NAMESPACE" \
  --set "image.tag=$WEAVIATE_VERSION" \
  --set replicas="$WEAVIATE_PODS" \
  $offload_secrets

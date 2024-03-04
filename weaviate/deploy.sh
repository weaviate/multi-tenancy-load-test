#!/bin/bash

cd "${0%/*}"

rm -rf "/tmp/weaviate-helm"
git clone -b raft-configuration https://github.com/weaviate/weaviate-helm.git "/tmp/weaviate-helm" 
helm package -d /tmp/weaviate-helm /tmp/weaviate-helm/weaviate 

kubectl create ns "$K8S_NAMESPACE" | true

helm upgrade \
  --install weaviate-load-test /tmp/weaviate-helm/weaviate-*.tgz \
  --values values.yaml \
  --namespace "$K8S_NAMESPACE" \
  --set "image.tag=$WEAVIATE_VERSION" \
  --set replicas="$WEAVIATE_PODS"



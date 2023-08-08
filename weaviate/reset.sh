#!/bin/bash

cd "${0%/*}"

helm delete weaviate-load-test --wait

kubectl get pvc -o 'jsonpath={.items[*].metadata.name}' -l app=weaviate | xargs kubectl delete pvc

./deploy.sh


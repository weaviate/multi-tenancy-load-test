#!/bin/bash

set -exo pipefail

cluster_name=mt-load-test
machine_type=e2-standard-4
initial_nodepool_size=12
region="us-central1"
zone="us-central1-c"

gcloud beta container \
  --project "semi-automated-benchmarking" clusters create "$cluster_name" \
  --zone "$zone" \
  --no-enable-basic-auth \
  --release-channel "regular" \
  --machine-type "$machine_type" \
  --image-type "COS_CONTAINERD" \
  --disk-type "pd-balanced" \
  --disk-size "100" \
  --metadata disable-legacy-endpoints=true \
  --scopes "https://www.googleapis.com/auth/devstorage.read_only","https://www.googleapis.com/auth/logging.write","https://www.googleapis.com/auth/monitoring","https://www.googleapis.com/auth/servicecontrol","https://www.googleapis.com/auth/service.management.readonly","https://www.googleapis.com/auth/trace.append" \
  --num-nodes "$initial_nodepool_size" \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM \
  --enable-ip-alias \
  --network "projects/semi-automated-benchmarking/global/networks/default" \
  --subnetwork "projects/semi-automated-benchmarking/regions/$region/subnetworks/default" \
  --no-enable-intra-node-visibility \
  --default-max-pods-per-node "110" \
  --no-enable-master-authorized-networks \
  --addons HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver \
  --enable-autoupgrade \
  --enable-autorepair \
  --max-surge-upgrade 1 \
  --max-unavailable-upgrade 0 \
  --no-enable-managed-prometheus \
  --enable-shielded-nodes \
  --node-locations "$zone"

gcloud container clusters get-credentials "$cluster_name" --zone "$zone" --project semi-automated-benchmarking

kubectl create ns "$K8S_NAMESPACE"

kubectl config set-context $(kubectl config current-context) --namespace $K8S_NAMESPACE

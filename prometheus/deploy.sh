#!/bin/bash

cd "${0%/*}"

helm upgrade --install observability . --values values.yaml



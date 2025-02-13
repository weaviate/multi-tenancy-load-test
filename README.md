# multi-tenancy-load-test

## Description

This project aims to perform load testing of multiple tenants in the Weaviate application. The main entry point for the project is `run.py`.

### Usage
- create your own branch out of https://github.com/weaviate/multi-tenancy-load-test/tree/raft
- update the image with your image tag [here](https://github.com/weaviate/multi-tenancy-load-test/blob/raft/cli_config.py#L108)
- push and it will run a pipeline [here](https://github.com/weaviate/multi-tenancy-load-test/actions)

## Local Trigger

This script creates resources on the Weaviate GCP project, please login first with:

```
gcloud auth application-default login
```

To run the load test, execute the following command:

```
python3 run.py
```

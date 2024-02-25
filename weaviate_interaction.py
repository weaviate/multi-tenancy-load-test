import weaviate


def client(host: str, grpc_host: str) -> weaviate.WeaviateClient:
    return weaviate.connect_to_custom(
        http_host=host,
        http_port=80,
        grpc_host=grpc_host,
        grpc_port=50051,
        http_secure=False,
        grpc_secure=False,
    )

import os
import weaviate
import weaviate.classes as wvc

primary_col_name = "TenaciousT"
ttl_col_name = "TTL"

host = os.getenv("HOST") or "localhost"
port = int(os.getenv("PORT") or 8080)
host_grpc = os.getenv("HOST_GRPC") or "localhost"
port_grpc = int(os.getenv("PORT_GRPC") or 50051)

client = weaviate.connect_to_custom(
    http_host=host,
    http_port=port,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=port_grpc,
    grpc_secure=False,
)

client.collections.delete_all()
client.collections.create(
    ttl_col_name,
    properties=[
        wvc.config.Property(
            name="tenant_name",
            data_type=wvc.config.DataType.TEXT,
            tokenization=wvc.config.Tokenization.FIELD,
        ),
        wvc.config.Property(name="expiration", data_type=wvc.config.DataType.DATE),
    ],
)

client.collections.create(
    primary_col_name,
    vector_index_config=wvc.config.Configure.VectorIndex.flat(
        distance_metric=wvc.config.VectorDistances.COSINE,
        quantizer=wvc.config.Configure.VectorIndex.Quantizer.bq(),
    ),
    multi_tenancy_config=wvc.config.Configure.multi_tenancy(True),
    vectorizer_config=None,
    replication_config=wvc.config.Configure.replication(factor=3),
)

client.close()

from pymilvus import MilvusClient, DataType, Function, FunctionType
import os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MILVUS_URI", "http://localhost:19530")
client = MilvusClient(uri=uri)
collection_name = "test_bm25_coll"

if client.has_collection(collection_name):
    client.drop_collection(collection_name)

schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=1000, enable_analyzer=True)
schema.add_field(field_name="sparse", datatype=DataType.SPARSE_FLOAT_VECTOR)

schema.add_function(Function(
    name="bm25",
    function_type=FunctionType.BM25,
    input_field_names=["content"],
    output_field_names=["sparse"]
))

client.create_collection(collection_name=collection_name, schema=schema)

index_params = client.prepare_index_params()
index_params.add_index(field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
client.create_index(collection_name, index_params)

client.load_collection(collection_name)
client.insert(collection_name, [{"content": "hello world this is a test"}])
client.flush(collection_name)

# search
res = client.search(
    collection_name=collection_name,
    data=["hello test"],
    anns_field="sparse",
    search_params={"metric_type": "BM25"}
)
print("Search results:")
print(res)

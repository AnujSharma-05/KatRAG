import os
from pymilvus import MilvusClient
uri = os.getenv("MILVUS_URI", "http://localhost:19530")
client = MilvusClient(uri=uri)
print(client.get_server_version())

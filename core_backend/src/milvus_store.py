import os
import time
from typing import Any

from .config import (
    MILVUS_URI, 
    MILVUS_COLLECTION,
    MILVUS_CATEGORIES_COLLECTION_NAME,
    MILVUS_INDEX_TYPE,
    MILVUS_M,
    MILVUS_EF_CONSTRUCTION,
    MILVUS_EF_SEARCH,
    EMBEDDING_DIM,
)

from pymilvus import MilvusClient, DataType, Function, FunctionType, AnnSearchRequest, RRFRanker

print("milvus_store import started")

class MilvusStore:
    """Small Milvus wrapper to keep vector DB operations isolated."""

    def __init__(self) -> None:
        self.collection_name = MILVUS_COLLECTION
        self.category_collection_name = "categorical_chunks"
        self.dim = EMBEDDING_DIM
        self._client: MilvusClient | None = None

    def _get_client(self) -> MilvusClient:

        if self._client is not None:
            return self._client

        uri = os.getenv("MILVUS_URI")

        if not uri:
            raise RuntimeError(
                "MILVUS_URI is not configured"
            )

        print(
            f"CONNECTED TO MILVUS SERVER: {uri}"
        )

        token = os.getenv("MILVUS_TOKEN")

        self._client = MilvusClient(
            uri=uri,
            token=token,
        )

        return self._client

    def _create_collection(self, client: MilvusClient, collection_name: str) -> None:
        schema = client.create_schema(
            auto_id=False,
            enable_dynamic_field=True
        )
        
        # Primary Key
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        # Vector Field
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.dim)
        
        if collection_name == self.collection_name:
            # Custom Scalar Fields for document chunks
            schema.add_field(field_name="organization_id", datatype=DataType.VARCHAR, max_length=64, is_partition_key=True)
            schema.add_field(field_name="document_id", datatype=DataType.INT64)
            schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
            # Enable analyzer for native BM25
            schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535, enable_analyzer=True)
            schema.add_field(field_name="is_current", datatype=DataType.BOOL, default_value=True)
            
            # Add sparse vector field for BM25
            schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
            # Add server-side BM25 function
            schema.add_function(Function(
                name="bm25",
                function_type=FunctionType.BM25,
                input_field_names=["content"],
                output_field_names=["sparse_vector"]
            ))
        else:
            # Custom Scalar Fields for categorical summaries
            schema.add_field(field_name="organization_id", datatype=DataType.VARCHAR, max_length=64, is_partition_key=True)
            schema.add_field(field_name="category_name", datatype=DataType.VARCHAR, max_length=255)
            schema.add_field(field_name="summary", datatype=DataType.VARCHAR, max_length=65535)
            schema.add_field(field_name="group_id", datatype=DataType.INT64, nullable=True)
        
        client.create_collection(
            collection_name=collection_name,
            schema=schema
        )
        
        # Prepare vector index
        index_params = client.prepare_index_params()
        
        idx_params = {"metric_type": "COSINE"}
        if MILVUS_INDEX_TYPE.upper() == "HNSW":
            idx_params["index_type"] = "HNSW"
            idx_params["params"] = {
                "M": MILVUS_M,
                "efConstruction": MILVUS_EF_CONSTRUCTION
            }
        else:
            idx_params["index_type"] = "AUTOINDEX"
            
        index_params.add_index(
            field_name="vector",
            **idx_params
        )
        
        if collection_name == self.collection_name:
            # Add sparse index for BM25
            index_params.add_index(
                field_name="sparse_vector",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="BM25"
            )

        client.create_index(
            collection_name=collection_name,
            index_params=index_params
        )
        print(f"CREATED COLLECTION & INDEX: {collection_name}")

    def ensure_collection(self) -> None: 
        client = self._get_client()

        # Document chunks
        if not client.has_collection(collection_name=self.collection_name):
            self._create_collection(client, self.collection_name)
        client.load_collection(collection_name=self.collection_name)

        # Categorical chunks
        if not client.has_collection(collection_name=self.category_collection_name):
            self._create_collection(client, self.category_collection_name)
        client.load_collection(collection_name=self.category_collection_name)
        print(f"ALL COLLECTIONS ENSURED & LOADED")

    def upsert_chunks(self, document_id: int, chunks: list[str], embeddings: list[list[float]], organization_id: str = "org_default") -> list[int]:
        self.ensure_collection()
        client = self._get_client()

        base_id = time.time_ns()
        data = [
            {
                "id": int(base_id + idx),
                "vector": embeddings[idx],
                "organization_id": organization_id,
                "document_id": document_id,
                "chunk_index": idx,
                "content": chunks[idx],
                "is_current": True,
            }
            for idx in range(len(chunks))
        ]
        print(
                f"INSERTING {len(chunks)} CHUNKS"
            )
        result = client.insert(collection_name=self.collection_name, data=data)
        client.load_collection(
            collection_name=self.collection_name
        )
        print(result)

        # Flush pushes the in-memory growing segment to sealed segments.
        client.flush(collection_name=self.collection_name)
        print(f"FLUSHED {len(chunks)} CHUNKS TO MILVUS")

        return [int(i) for i in result.get("ids", [])]

    def search(self, query_text: str, query_embedding: list[float], top_k: int = 5, document_id: int | None = None, document_ids: list[int] | None = None, organization_id: str = "org_default", valid_document_ids: list[str] | None = None, is_temporal: bool = False) -> list[dict[str, Any]]:
        self.ensure_collection()  # also loads the collection
        client = self._get_client()
        ef_value = max(MILVUS_EF_SEARCH, top_k)
        
        filters = [f"organization_id == '{organization_id}'"]
        
        if is_temporal and valid_document_ids is not None:
            if not valid_document_ids:
                return []
            ids_str = ", ".join(str(i) for i in valid_document_ids)
            filters.append(f"document_id in [{ids_str}]")
        else:
            filters.append("is_current == true")
            if document_id is not None:
                filters.append(f"document_id == {document_id}")
            elif document_ids is not None:
                if document_ids:
                    ids_str = ", ".join(str(i) for i in document_ids)
                    filters.append(f"document_id in [{ids_str}]")
                else:
                    return []

        filter_expr = " and ".join(filters)

        # Dense search request
        dense_req = AnnSearchRequest(
            data=[query_embedding],
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"ef": ef_value}},
            limit=top_k,
            expr=filter_expr
        )
        
        # Sparse search request (natively computed via BM25 function)
        sparse_req = AnnSearchRequest(
            data=[query_text],
            anns_field="sparse_vector",
            param={"metric_type": "BM25"},
            limit=top_k,
            expr=filter_expr
        )
        
        # Hybrid Search with RRFRanker
        results = client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(k=60),
            limit=top_k,
            output_fields=["document_id", "chunk_index", "content", "organization_id", "is_current"]
        )

        formatted: list[dict[str, Any]] = []
        if results and results[0]:
            for hit in results[0]:
                entity = hit.get("entity", {})
                formatted.append(
                    {
                        "milvus_id": int(hit.get("id")),
                        "score": float(hit.get("distance", 0.0)),
                        "document_id": int(entity.get("document_id")),
                        "chunk_index": int(entity.get("chunk_index")),
                        "content": str(entity.get("content")),
                    }
                )
        return formatted

    def deprecate_document_vectors(self, document_id: int, organization_id: str) -> None:
        self.ensure_collection()
        client = self._get_client()
        
        filter_expr = f"document_id == {document_id} and organization_id == '{organization_id}' and is_current == true"
        res = client.query(
            collection_name=self.collection_name,
            filter=filter_expr,
            output_fields=["id", "vector", "organization_id", "document_id", "chunk_index", "content"]
        )
        
        if not res:
            print(f"NO ACTIVE VECTORS FOUND FOR DOC {document_id}")
            return
            
        print(f"DEPRECATING {len(res)} VECTORS FOR DOC {document_id}")
        
        ids_to_delete = [hit["id"] for hit in res]
        ids_str = ", ".join(str(i) for i in ids_to_delete)
        
        client.delete(
            collection_name=self.collection_name,
            filter=f"id in [{ids_str}]"
        )
        
        data = []
        for hit in res:
            new_hit = dict(hit)
            new_hit["is_current"] = False
            data.append(new_hit)
            
        client.insert(collection_name=self.collection_name, data=data)
        client.flush(collection_name=self.collection_name)
        print(f"SUCCESSFULLY DEPRECATED {len(data)} VECTORS FOR DOC {document_id}")

    def delete_document_chunks(self, document_id: int) -> None:
        self.ensure_collection()
        client = self._get_client()
        client.delete(collection_name=self.collection_name, filter=f"document_id == {document_id}")

    def delete_category_summary(self, category_name: str, group_id: int | None = None) -> None:
        self.ensure_collection()
        client = self._get_client()
        filter_str = f"category_name == '{category_name}'"
        if group_id is not None:
            filter_str += f" and group_id == {group_id}"
        client.delete(
            collection_name=self.category_collection_name,
            filter=filter_str
        )
        print(f"DELETED SUMMARY FOR CATEGORY: {category_name} (Group: {group_id})")

    def upsert_category_summary(self, category_name: str, summary: str, embedding: list[float], group_id: int | None = None) -> None:
        self.ensure_collection()
        client = self._get_client()

        # Clean existing summaries for this category and group
        filter_str = f"category_name == '{category_name}'"
        if group_id is not None:
            filter_str += f" and group_id == {group_id}"
        
        client.delete(
            collection_name=self.category_collection_name,
            filter=filter_str
        )

        base_id = time.time_ns()
        data = [
            {
                "id": int(base_id),
                "vector": embedding,
                "category_name": category_name,
                "summary": summary,
                "group_id": group_id if group_id is not None else 0
            }
        ]
        client.insert(collection_name=self.category_collection_name, data=data)
        client.flush(collection_name=self.category_collection_name)
        print(f"UPSERTED SUMMARY FOR CATEGORY: {category_name} (Group: {group_id})")

    def search_categories(self, query_embedding: list[float], top_k: int = 5, group_id: int | None = None) -> list[dict[str, Any]]:
        self.ensure_collection()
        client = self._get_client()
        ef_value = max(MILVUS_EF_SEARCH, top_k)
        search_kwargs: dict[str, Any] = {
            "collection_name": self.category_collection_name,
            "data": [query_embedding],
            "limit": top_k,
            "output_fields": ["category_name", "summary", "group_id"],
            "search_params": {"metric_type": "COSINE", "params": {"ef": ef_value}}
        }
        
        if group_id is not None:
            search_kwargs["filter"] = f"group_id == {group_id}"
            
        results = client.search(**search_kwargs)

        formatted: list[dict[str, Any]] = []
        if results and results[0]:
            for hit in results[0]:
                entity = hit.get("entity", {})
                formatted.append(
                    {
                        "category_name": str(entity.get("category_name")),
                        "summary": str(entity.get("summary")),
                        "group_id": int(entity.get("group_id")) if entity.get("group_id") is not None else None,
                        "score": float(hit.get("distance", 0.0))
                    }
                )
        return formatted

    # def delete_all_chunks(self) -> None:
    #     client = self._get_client()

    #     if client.has_collection(
    #         collection_name=self.collection_name
    #     ):
    #         client.drop_collection(
    #             collection_name=self.collection_name
    #         )

    #     client.create_collection(
    #         collection_name=self.collection_name,
    #         dimension=self.dim,
    #     )

    def delete_all_chunks(self) -> None:
        client = self._get_client()
        for col in [self.collection_name, self.category_collection_name]:
            if client.has_collection(collection_name=col):
                client.drop_collection(collection_name=col)
            self._create_collection(client, col)
        print("ALL MILVUS DATA WIPED")

print("creating milvus_store singleton")

milvus_store = MilvusStore()

print("milvus_store singleton created")




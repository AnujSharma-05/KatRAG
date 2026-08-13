from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Float, Boolean, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from .database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=lambda: f"org_{uuid.uuid4().hex[:12]}")
    name = Column(String, nullable=False)
    plan_tier = Column(String, default="free")
    status = Column(String, default="active")
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    groups = relationship("Group", back_populates="organization")

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="groups")
    creator = relationship("User", back_populates="created_groups")
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="group", cascade="all, delete-orphan")

class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="memberships")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="member")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    created_groups = relationship("Group", back_populates="creator")
    memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    documents = relationship("Document", secondary="document_categories", back_populates="categories")
    group = relationship("Group")

class DocumentCategory(Base):
    __tablename__ = "document_categories"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False, index=True)

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    filename = Column(String, index=True)
    file_size = Column(Integer, nullable=True)
    file_path = Column(String)
    status = Column(String, default="uploaded")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True)
    
    group = relationship("Group", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    categories = relationship("Category", secondary="document_categories", back_populates="documents")

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String, primary_key=True, default=lambda: f"ver_{uuid.uuid4().hex[:12]}")
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False, default=1)
    content_hash = Column(String, nullable=True, index=True)
    object_key = Column(String, nullable=True)
    status = Column(String, default="indexed")
    valid_from = Column(DateTime, default=datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    authority_score = Column(Float, default=0.5)
    index_version = Column(Integer, default=1)

    document = relationship("Document", back_populates="versions")
    chunks = relationship("DocumentChunk", back_populates="version")

class DocumentChunk(Base): 
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_version_id = Column(String, ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=True, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    milvus_id = Column(String, nullable=True, index=True)
    
    # Citation & Enrichment fields
    char_start = Column(Integer, default=0)
    char_end = Column(Integer, default=0)
    page_from = Column(Integer, nullable=True)
    section_path = Column(String, nullable=True)
    context_prefix = Column(Text, nullable=True)
    parent_chunk_id = Column(Integer, ForeignKey("document_chunks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")
    version = relationship("DocumentVersion", back_populates="chunks")

class QueryTrace(Base):
    __tablename__ = "query_traces"

    id = Column(String, primary_key=True, default=lambda: f"trc_{uuid.uuid4().hex[:12]}")
    trace_id = Column(String, nullable=False, index=True)
    organization_id = Column(String, nullable=True, index=True)
    group_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)
    query_text = Column(Text, nullable=False)
    routed_categories = Column(JSON, nullable=True)
    candidate_ids = Column(JSON, nullable=True)
    final_chunk_ids = Column(JSON, nullable=True)
    top_score = Column(Float, nullable=True)
    gate_decision = Column(String, nullable=True)
    latency_ms = Column(JSON, nullable=True)
    grounding_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


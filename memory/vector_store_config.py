#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# file >> vector_store_config.py
# project >> SupremeAI 2.0
# purpose >> Configuration loading
# module >> memory
# ============================================================================
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class VectorStoreConfig:
    backend: str = "chroma"
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    pinecone_api_key: Optional[str] = None
    pinecone_index: Optional[str] = None
    default_collection: str = "supremeai_default"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    distance: str = "cosine"


def get_vector_store_config() -> VectorStoreConfig:
    return VectorStoreConfig(
        backend=os.getenv("VECTOR_BACKEND", "chroma"),
        qdrant_url=os.getenv("QDRANT_URL"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        pinecone_api_key=os.getenv("PINECONE_API_KEY"),
        pinecone_index=os.getenv("PINECONE_INDEX"),
    )

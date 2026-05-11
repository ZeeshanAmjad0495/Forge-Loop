"""Optional smoke test against a real MongoDB instance (Task 40A).

Skipped by default. Enable with::

    FORGELOOP_RUN_MONGO_INTEGRATION_TESTS=true \\
        MONGODB_URI=mongodb://localhost:27017 \\
        pytest tests/test_repositories_mongo_integration.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("FORGELOOP_RUN_MONGO_INTEGRATION_TESTS", "").lower() != "true",
    reason="real-mongo integration tests are disabled (set "
    "FORGELOOP_RUN_MONGO_INTEGRATION_TESTS=true to enable)",
)


def test_real_mongo_save_get_roundtrip():
    pymongo = pytest.importorskip("pymongo")
    from app import repositories_mongo as mongo
    from app.models import Project

    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    db = client["forgeloop_integration_test"]
    db.drop_collection("projects")

    repo = mongo.MongoProjectRepository(db)
    now = datetime(2026, 5, 12, tzinfo=timezone.utc)
    project = Project(
        id="int-1",
        name="integration",
        description="real-mongo smoke",
        created_at=now,
        updated_at=now,
    )
    repo.save(project)
    loaded = repo.get("int-1")
    assert loaded == project

    db.drop_collection("projects")

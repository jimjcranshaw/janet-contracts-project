import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.workers.ingestion_worker import IngestionWorker
from app.models import Notice, Buyer, IngestionLog

def test_ingestion_worker_run(db):
    """
    Test the full ingestion worker run with mocked FTS client.
    """
    # Sample OCDS Data
    sample_release = {
        "ocid": "ocds-b5fd17-12345",
        "id": "release-1",
        "date": "2023-10-01T10:00:00Z",
        "tag": ["contractNotice"],
        "buyer": {
            "name": "  Test Buyer  ",
            "identifier": {"id": "GB-COH-1234"}
        },
        "tender": {
            "title": "Test Tender",
            "description": "A description",
            "value": {"amount": 10000, "currency": "GBP"},
            "tenderPeriod": {"endDate": "2023-12-01T10:00:00Z"}
        }
    }

    # Mock the FTS Client
    with patch('app.workers.ingestion_worker.FTSClient') as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.fetch_releases.return_value = [sample_release]

        # Patch Postgres insert with SQLite insert for compatibility
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        with patch('app.workers.ingestion_worker.insert', side_effect=sqlite_insert):
            # Initialize and Run Worker
            worker = IngestionWorker()
            
            # Override DB session creation to use our test fixture
            with patch('app.workers.ingestion_worker.SessionLocal', return_value=db):
                worker.run()

    # Assertions
    # 1. Log Check
    log = db.query(IngestionLog).first()
    assert log is not None
    assert log.status == "SUCCESS"
    assert log.items_processed == 1

    # 2. Buyer Check
    buyer = db.query(Buyer).filter_by(slug="test-buyer").first()
    assert buyer is not None
    assert buyer.canonical_name == "Test Buyer"

    # 3. Notice Check
    notice = db.query(Notice).filter_by(ocid="ocds-b5fd17-12345").first()
    assert notice is not None
    assert notice.title == "Test Tender"
    assert notice.value_amount == 10000
    assert notice.buyer_id == buyer.id

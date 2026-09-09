from voiceguard.ledger import HeardStateLedger


def test_ledger_tracks_generated_and_played():
    ledger = HeardStateLedger()
    ledger.generated(1, "hello")
    ledger.chunk_generated(1, 0)
    ledger.chunk_played(1, 0)
    ledger.chunk_generated(1, 1)
    ledger.chunk_rejected(1, 1, "superseded")

    assert ledger.played_sequences(1) == [0]
    assert len(ledger.events_for(1)) == 5


def test_request_entry_is_compact_and_tracks_heard_state():
    ledger = HeardStateLedger()
    ledger.request_started(1, "Find trains to Delhi")
    ledger.generated(1, "The next train leaves at 08:10.")
    ledger.chunk_generated(1, 0)
    ledger.chunk_played(1, 0)
    ledger.chunk_generated(1, 1)
    ledger.chunk_rejected(1, 1, "superseded")
    ledger.interrupted(1, 2, "user_interrupt")

    entry = ledger.request_entry(1)

    assert entry == {
        "request_id": 1,
        "generated_text": "The next train leaves at 08:10.",
        "played_chunks": 1,
        "rejected_chunks": 1,
        "interrupted": True,
        "interrupt_at": entry["interrupt_at"],
        "status": "SUPERSEDED",
    }


def test_request_entries_returns_one_entry_per_request():
    ledger = HeardStateLedger()
    ledger.request_started(2, "new")
    ledger.request_started(1, "old")
    assert [entry["request_id"] for entry in ledger.request_entries()] == [1, 2]

"""
Test script for profile extraction pipeline
Tests the integration of ProfileExtractor and ProfileStorageService in the unified ingestion graph
"""

import sys
from src.schemas import TranscriptRequest, Message
from src.services.unified_ingestion_graph import run_unified_ingestion
from src.services.profile_storage import ProfileStorageService


def test_profile_extraction():
    """Test profile extraction from a conversation"""

    # Create a conversation with profile-worthy content
    user_id = "test_user_profile_001"

    history = [
        Message(
            role="user",
            content="Hi, I'm Alice and I work as a software engineer in San Francisco.",
        ),
        Message(
            role="assistant",
            content="Nice to meet you, Alice! How's the tech scene in SF?",
        ),
        Message(
            role="user",
            content="It's great! I've been coding in Python for 5 years now and I really enjoy it. My goal this year is to learn more about AI and machine learning.",
        ),
        Message(
            role="assistant",
            content="That's awesome! What kind of projects are you working on?",
        ),
        Message(
            role="user",
            content="I'm building a personal finance app. I love hiking in my free time and exploring new restaurants.",
        ),
    ]

    request = TranscriptRequest(
        user_id=user_id, history=history, metadata={"test": True}
    )

    print(f"[TEST] Running ingestion for user_id={user_id}")
    print(f"[TEST] Conversation has {len(history)} messages")

    # Run the unified ingestion graph
    try:
        final_state = run_unified_ingestion(request)

        # Check results
        print("\n=== INGESTION RESULTS ===")
        print(f"Worthy: {final_state.get('worthy', False)}")
        print(f"Extracted items: {len(final_state.get('extracted_items', []))}")
        print(f"Memories created: {len(final_state.get('memory_ids', []))}")
        print(f"Profile extractions: {len(final_state.get('profile_extractions', []))}")

        # Print profile extractions
        extractions = final_state.get("profile_extractions", [])
        if extractions:
            print("\n=== PROFILE EXTRACTIONS ===")
            for i, extraction in enumerate(extractions, 1):
                print(
                    f"\n{i}. {extraction.get('category')} / {extraction.get('field_name')}"
                )
                print(f"   Value: {extraction.get('field_value')}")
                print(f"   Confidence: {extraction.get('confidence')}%")
                print(f"   Source Type: {extraction.get('source_type')}")

        # Print storage results
        storage_results = final_state.get("storage_results", {})
        print("\n=== STORAGE RESULTS ===")
        print(f"ChromaDB stored: {storage_results.get('chromadb_stored', 0)}")
        print(
            f"Profile fields stored: {storage_results.get('profile_fields_stored', 0)}"
        )
        print(f"Episodic stored: {storage_results.get('episodic_stored', 0)}")
        print(f"Emotional stored: {storage_results.get('emotional_stored', 0)}")

        # Retrieve profile to verify storage
        print("\n=== RETRIEVING PROFILE ===")
        storage = ProfileStorageService()
        profile = storage.get_profile_by_user(user_id)

        if profile:
            print(f"User ID: {profile['user_id']}")
            print(f"Completeness: {profile['completeness_pct']:.1f}%")
            print(
                f"Populated fields: {profile['populated_fields']}/{profile['total_fields']}"
            )

            print("\n=== PROFILE DATA ===")
            for category, fields in profile["profile"].items():
                if fields:
                    print(f"\n{category.upper()}:")
                    for field_name, field_data in fields.items():
                        print(f"  - {field_name}: {field_data['value']}")
        else:
            print("No profile found!")

        # Check for errors
        errors = final_state.get("errors", [])
        if errors:
            print("\n=== ERRORS ===")
            for error in errors:
                print(f"ERROR: {error}")

        # Print metrics
        metrics = final_state.get("metrics", {})
        print("\n=== METRICS ===")
        print(f"Total time: {metrics.get('total_ms', 0)}ms")
        print(f"Worthiness check: {metrics.get('worthiness_check_ms', 0)}ms")
        print(f"Extraction: {metrics.get('extraction_ms', 0)}ms")
        print(f"Classification: {metrics.get('classification_ms', 0)}ms")

        print("\n✅ Test completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_profile_extraction()
    sys.exit(0 if success else 1)

"""
Quick test script for Atlas Intelligence API
Run: python test_api.py
"""

import asyncio
import sys
from services.threat_classifier import get_threat_classifier
from services.visual_detector import get_visual_detector


async def test_threat_classifier():
    """Test threat classification"""
    print("\n" + "="*60)
    print("Testing Threat Classifier")
    print("="*60)

    classifier = await get_threat_classifier()

    # Test cases
    test_cases = [
        "Someone is attacking people with a knife on the street",
        "Loud noise complaint from neighbors",
        "Car was stolen from parking lot",
        "Group of people fighting outside the bar",
        "Gunshots heard near the school"
    ]

    for i, description in enumerate(test_cases, 1):
        print(f"\n[Test {i}] Description: \"{description}\"")
        result = await classifier.classify_text(description)

        print(f"  → Category: {result['threat_category']}")
        print(f"  → Severity: {result['severity']}/5")
        print(f"  → Confidence: {result['confidence']:.2f}")
        print(f"  → Halo type: {result['product_mappings']['halo_incident_type']}")
        print(f"  → Keywords: {result.get('keywords_matched', [])}")


async def test_visual_detector():
    """Test visual detector (without actual image)"""
    print("\n" + "="*60)
    print("Testing Visual Detector")
    print("="*60)

    detector = await get_visual_detector()

    print(f"\n  Model loaded: {detector.loaded}")
    print(f"  Model path: {detector.model_path}")
    print(f"  Device: {detector.device}")

    if detector.loaded:
        print("  ✅ YOLOv8 ready for inference")
    else:
        print("  ⚠️  Using mock detection (YOLOv8 not available)")


async def test_services():
    """Run all service tests"""
    try:
        await test_threat_classifier()
        await test_visual_detector()

        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
        print("\nNext steps:")
        print("  1. Start the API: uvicorn main:app --reload")
        print("  2. Visit http://localhost:8001/docs")
        print("  3. Test endpoints via Swagger UI")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_services())

import os
import json
import requests

docs = [
    ("UK Residence Permit", "6aa6caf7-de34-42be-99af-20afa8f147d9.jpeg"),
    ("Brazilian Passport on Brick", "3c5389a7-a5b1-4a76-b2d5-590d78682041.png"),
    ("United States Passport Card", "104099e6-7850-4042-a005-b2c0ef34974b.jpeg"),
    ("United Kingdom Passport", "47440e8a-55f0-4757-9651-2e7449b198c4.jpeg"),
    ("US Permanent Resident Card", "02a211b0-7e04-4ff3-8ac1-2f69abc29e9d.jpeg")
]

print("=" * 70)
print("=== 5-DOCUMENT END-TO-END VERIFICATION BENCHMARK ===")
print("=" * 70 + "\n")

for i, (label, doc) in enumerate(docs, 1):
    file_path = os.path.abspath(os.path.join("uploads", doc))
    if not os.path.exists(file_path):
        print(f"Doc {i} ({label}): {doc} NOT FOUND")
        continue

    # Upload with document_type='auto'
    with open(file_path, "rb") as f:
        up_res = requests.post(
            "http://127.0.0.1:8000/api/upload",
            files={"file": (doc, f, "image/jpeg")},
            data={"document_type": "auto"}
        )
    if up_res.status_code != 200:
        print(f"Doc {i} ({label}): Upload failed: {up_res.text}")
        continue
    file_id = up_res.json()["file_id"]

    # Analyze document
    an_res = requests.post(f"http://127.0.0.1:8000/api/analyze/{file_id}")
    if an_res.status_code != 200:
        print(f"Doc {i} ({label}): Analysis failed: {an_res.text}")
        continue

    data = an_res.json()
    receipt = data.get("blockchain_receipt", {})
    tampering = data.get("tampering", {})
    ai_det = tampering.get("ai_detection", {})
    fields = data.get("extracted_fields", {})

    print(f"--- DOCUMENT {i}: {label} ({doc}) ---")
    print(f"  Auto-Detected Type : {receipt.get('document_type')}")
    print(f"  Risk Score / Level : {data.get('overall_risk_score')} / {str(data.get('overall_risk_level', '')).upper()}")
    print(f"  Decision           : {data.get('decision')}")
    print(f"  HF ViT Model       : {ai_det.get('model_name')} -> {ai_det.get('label')} (Score: {ai_det.get('ai_generated_likelihood')}%)")
    print(f"  Extracted Fields   : {fields}")
    print(f"  Summary Flags      : {data.get('summary_flags')}")
    print()

import langextract as lx
import textwrap
from config import get_config
import json
import os
import sys
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("="*60)
print("LangExtract - Download + Local Processing + Real-time Save")
print("="*60)

# Prompt and examples
prompt = textwrap.dedent("""\
    Extract characters, emotions, and relationships in order of appearance.
    Use exact text for extractions. Do not paraphrase or overlap entities.
    For attributes, provide simple string values only.""")

examples = [
    lx.data.ExampleData(
        text="ROMEO. But soft! What light through yonder window breaks? It is the east, and Juliet is the sun.",
        extractions=[
            lx.data.Extraction("character", "ROMEO", attributes={"role": "protagonist"}),
            lx.data.Extraction("emotion", "But soft!", attributes={"type": "wonder"}),
            lx.data.Extraction("relationship", "Juliet is the sun", attributes={"type": "adoration"}),
        ]
    )
]

# Config
config_dict = get_config()
print(f"\nModel: {config_dict['model']}")
print(f"Endpoint: {config_dict.get('base_url', 'default')}")

provider_kwargs = {k: v for k, v in config_dict.items() if k != 'model'}

# === STEP 1: Download file to local disk ===
print("\n" + "="*60)
print("STEP 1: Download Text")
print("="*60)

url = "https://www.gutenberg.org/files/1513/1513-0.txt"
local_file = "data/romeo_juliet.txt"

os.makedirs("data", exist_ok=True)

if not os.path.exists(local_file):
    print(f"Downloading from: {url}")
    try:
        # Use requests to download
        import requests
        response = requests.get(url, timeout=10)
        with open(local_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"[OK] Downloaded to: {local_file}")
        print(f"[OK] File size: {len(response.text):,} characters")
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
else:
    with open(local_file, 'r', encoding='utf-8') as f:
        file_content = f.read()
    print(f"[OK] File already exists: {local_file}")
    print(f"[OK] File size: {len(file_content):,} characters")

# === STEP 2: Read from local file ===
print("\n" + "="*60)
print("STEP 2: Read from Local File")
print("="*60)

with open(local_file, 'r', encoding='utf-8') as f:
    text_content = f.read()

print(f"[OK] Read {len(text_content):,} characters")

# === STEP 3: Split text into chunks for processing ===
print("\n" + "="*60)
print("STEP 3: Process Text in Chunks")
print("="*60)

output_dirpath = os.path.join("demo_output", "demoV2_local")
os.makedirs(output_dirpath, exist_ok=True)

output_file = os.path.join(output_dirpath, "extraction_results.jsonl")
csv_file = os.path.join(output_dirpath, "extraction_results.csv")

# Clear files
open(output_file, 'w', encoding='utf-8').close()
open(csv_file, 'w', encoding='utf-8').close()

# Write header for CSV
with open(csv_file, 'w', encoding='utf-8') as f:
    f.write("chunk_id\tclass\ttext\tattributes\n")

print(f"Output files:")
print(f"  - {output_file}")
print(f"  - {csv_file}")

# Real-time writer
def write_extraction_realtime(chunk_id, extraction, idx):
    """Write extraction in real-time"""
    # Simple format for streaming
    record = {
        "chunk_id": chunk_id,
        "idx": idx,
        "class": extraction.extraction_class,
        "text": extraction.extraction_text,
        "position": {
            "start": extraction.char_interval.start_pos if extraction.char_interval else None,
            "end": extraction.char_interval.end_pos if extraction.char_interval else None,
        } if extraction.char_interval else None,
        "alignment": extraction.alignment_status.value if extraction.alignment_status else None,
        "attributes": extraction.attributes
    }
    
    # JSONL (streaming format)
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')
    
    # CSV
    attrs_json = json.dumps(extraction.attributes or {}, ensure_ascii=False)
    csv_line = f"{chunk_id}\t{extraction.extraction_class}\t{extraction.extraction_text}\t{attrs_json}\n"
    with open(csv_file, 'a', encoding='utf-8') as f:
        f.write(csv_line)
    
    print(f"  [{idx}] {extraction.extraction_class}: {extraction.extraction_text}")

# Store all results for visualization-compatible format
all_documents = []

# Split text into chunks (first 3 paragraphs each)
paragraphs = text_content.split('\n\n')
chunk_size = 3
chunks = ['\n\n'.join(paragraphs[i:i+chunk_size]) for i in range(0, len(paragraphs), chunk_size)]

print(f"[OK] Split into {len(chunks)} chunks")
print("\nProcessing chunks...")
print("-" * 60)

total_extractions = 0

for chunk_id, chunk in enumerate(chunks[:5], 1):  # Process only first 5 chunks for demo
    if not chunk.strip():
        continue
    
    print(f"\n[Chunk {chunk_id}] Processing {len(chunk)} characters...")
    
    try:
        result = lx.extract(
            text_or_documents=chunk,
            prompt_description=prompt,
            examples=examples,
            config=lx.factory.ModelConfig(
                model_id=config_dict["model"],
                provider_kwargs=provider_kwargs
            ),
            extraction_passes=1,
            max_workers=5,
            max_char_buffer=2000,
            show_progress=False
        )
        
        if result.extractions:
            for i, extraction in enumerate(result.extractions, 1):
                write_extraction_realtime(chunk_id, extraction, i)
                total_extractions += 1
            
            # Store result for visualization
            all_documents.append(result)
        else:
            print("  (No extractions)")
            
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {str(e)[:80]}")
        continue

# === STEP 4: Display results ===
print("\n" + "="*60)
print("RESULTS SUMMARY")
print("="*60)
print(f"Total extractions: {total_extractions}")
print(f"\nOutput files:")
print(f"  - {output_file}")
print(f"  - {csv_file}")

print("\n" + "="*60)
print("SAVED EXTRACTIONS (JSONL)")
print("="*60)

if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            record = json.loads(line)
            print(f"{i}. [Chunk {record['chunk_id']}] {record['class']}: {record['text']}")

# === STEP 5: Save in LangExtract-compatible format for visualization ===
print("\n" + "="*60)
print("STEP 5: Save in LangExtract Format")
print("="*60)

# Save in standard LangExtract JSONL format for visualize()
if all_documents:
    lx_jsonl_file = os.path.join(output_dirpath, "extraction_results.jsonl")
    try:
        lx.io.save_annotated_documents(all_documents, output_name="extraction_results.jsonl", output_dir=output_dirpath)
        print(f"[OK] Saved LangExtract format: {lx_jsonl_file}")
        
        # === STEP 6: Generate HTML visualization ===
        print("\n" + "="*60)
        print("STEP 6: Generate HTML Visualization")
        print("="*60)
        
        html_file = os.path.join(output_dirpath, "visualization.html")
        try:
            html_content = lx.visualize(lx_jsonl_file)
            with open(html_file, "w", encoding="utf-8") as f:
                if hasattr(html_content, 'data'):
                    f.write(html_content.data)
                else:
                    f.write(html_content)
            print(f"[OK] Generated visualization: {html_file}")
        except Exception as e:
            print(f"[WARN] Could not generate visualization: {e}")
    except Exception as e:
        print(f"[WARN] Could not save in LangExtract format: {e}")

print("\n" + "="*60)
print("COMPLETE - Real-time Processing Done!")
print("="*60)
print(f"\nSummary:")
print(f"  Total chunks: {len(chunks[:5])}")
print(f"  Total extractions: {total_extractions}")
print(f"  Output directory: {output_dirpath}")

import langextract as lx
import textwrap
from config import get_config
import os
import json
from pathlib import Path
from langextract import data_lib

print("="*60)
print("LangExtract Demo - Real-time Processing and Saving")
print("="*60)

# 1. Define the prompt and extraction rules
prompt = textwrap.dedent("""\
    Extract characters, emotions, and relationships in order of appearance.
    Use exact text for extractions. Do not paraphrase or overlap entities.
    For each extraction, provide simple string attributes only.""")

# 2. Define examples
examples = [
    lx.data.ExampleData(
        text="ROMEO. But soft! What light through yonder window breaks? It is the east, and Juliet is the sun.",
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="ROMEO",
                attributes={"role": "protagonist"}
            ),
            lx.data.Extraction(
                extraction_class="emotion",
                extraction_text="But soft!",
                attributes={"type": "wonder"}
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Juliet is the sun",
                attributes={"type": "metaphor"}
            ),
        ]
    )
]

# Load configuration
config_dict = get_config()
print(f"\nUsing model: {config_dict['model']}")
if 'base_url' in config_dict:
    print(f"API endpoint: {config_dict['base_url']}")

# Prepare provider kwargs
provider_kwargs = {k: v for k, v in config_dict.items() if k != 'model'}

# Create output directory
output_dirpath = "demo_output/demoV4_realtime"
os.makedirs(output_dirpath, exist_ok=True)

# Initialize JSONL file
output_file = os.path.join(output_dirpath, "extraction_results_stream.jsonl")
csv_file = os.path.join(output_dirpath, "extraction_results.csv")

# Clear previous files
open(output_file, 'w', encoding='utf-8').close()
open(csv_file, 'w', encoding='utf-8').close()

print(f"\nOutput files:")
print(f"  JSONL: {output_file}")
print(f"  CSV:   {csv_file}")
print("-" * 60)

# Real-time writer function
def write_extraction_realtime(extraction, document_id, index):
    """Write extraction to file in real-time"""
    # JSONL format: one JSON object per line
    extraction_dict = {
        "document_id": document_id,
        "extraction_index": index,
        "class": extraction.extraction_class,
        "text": extraction.extraction_text,
        "position": {
            "start": extraction.char_interval.start_pos if extraction.char_interval else None,
            "end": extraction.char_interval.end_pos if extraction.char_interval else None,
        } if extraction.char_interval else None,
        "alignment": extraction.alignment_status.value if extraction.alignment_status else None,
        "attributes": extraction.attributes
    }
    
    # Append to JSONL
    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(extraction_dict, ensure_ascii=False) + '\n')
    
    # Append to CSV
    with open(csv_file, 'a', encoding='utf-8') as f:
        attrs_str = json.dumps(extraction.attributes, ensure_ascii=False) if extraction.attributes else ""
        line = f"{document_id}\t{extraction.extraction_class}\t{extraction.extraction_text}\t{attrs_str}\n"
        f.write(line)
    
    print(f"  [{index}] {extraction.extraction_class}: {extraction.extraction_text}")

# Sample texts to process
texts = [
    ("text_001", """
ROMEO. But soft! What light through yonder window breaks?
It is the east, and Juliet is the sun.
Arise, fair sun, and kill the envious moon.
    """),
    ("text_002", """
JULIET. O Romeo, Romeo! Wherefore art thou Romeo?
Deny thy father and refuse thy name.
What's in a name? That which we call a rose
By any other name would smell as sweet.
    """),
    ("text_003", """
ROMEO. Shall I hear more, or shall I speak at this?
JULIET. 'Tis but thy name that is my enemy.
Thou art thyself, though not a Montague.
    """)
]

print("\nProcessing documents with real-time output...\n")

total_extractions = 0

for doc_id, text in texts:
    print(f"\n[Processing: {doc_id}]")
    
    try:
        result = lx.extract(
            text_or_documents=text,
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
        
        # Write extractions in real-time
        if result.extractions:
            for i, extraction in enumerate(result.extractions, 1):
                write_extraction_realtime(extraction, doc_id, i)
                total_extractions += 1
        else:
            print("  (No extractions found)")
            
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {str(e)[:100]}")
        continue

print("\n" + "="*60)
print("REAL-TIME PROCESSING COMPLETE")
print("="*60)
print(f"Total documents: {len(texts)}")
print(f"Total extractions: {total_extractions}")
print(f"\nOutput files:")
print(f"  - {output_file}")
print(f"  - {csv_file}")

# Display file contents
print("\n" + "="*60)
print("SAVED RESULTS (JSONL)")
print("="*60)
if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            data = json.loads(line)
            print(f"{i}. [{data['document_id']}] {data['class']}: {data['text']}")

print("\n" + "="*60)
print("SUCCESS: Real-time streaming complete!")
print("="*60)


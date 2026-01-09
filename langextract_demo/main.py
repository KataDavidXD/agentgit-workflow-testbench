import langextract as lx
import textwrap
from config import get_config
import os
# 1. Define the prompt and extraction rules
prompt = textwrap.dedent("""\
    Extract characters, emotions, and relationships in order of appearance.
    Use exact text for extractions. Do not paraphrase or overlap entities.
    Provide meaningful attributes for each entity to add context.""")

# 2. Provide a high-quality example to guide the model
examples = [
    lx.data.ExampleData(
        text="ROMEO. But soft! What light through yonder window breaks? It is the east, and Juliet is the sun.",
        extractions=[
            lx.data.Extraction(
                extraction_class="character",
                extraction_text="ROMEO",
                attributes={"emotional_state": "wonder"}
            ),
            lx.data.Extraction(
                extraction_class="emotion",
                extraction_text="But soft!",
                attributes={"feeling": "gentle awe"}
            ),
            lx.data.Extraction(
                extraction_class="relationship",
                extraction_text="Juliet is the sun",
                attributes={"type": "metaphor"}
            ),
        ]
    )
]


# The input text to be processed
input_text = "Lady Juliet gazed longingly at the stars, her heart aching for Romeo"

# Load configuration
config_dict = get_config()
print(f"Using model: {config_dict['model']}")
if 'base_url' in config_dict:
    print(f"API endpoint: {config_dict['base_url']}")

# Prepare provider kwargs (remove 'model' key as it's not a provider param)
provider_kwargs = {k: v for k, v in config_dict.items() if k != 'model'}

# Run the extraction
result = lx.extract(
    text_or_documents=input_text,
    prompt_description=prompt,
    examples=examples,
    config=lx.factory.ModelConfig(
        model_id=config_dict["model"],
        provider_kwargs=provider_kwargs
    )
)



output_dirpath="demo_output/demoV1"
os.makedirs(output_dirpath, exist_ok=True)
# Save the results to a JSONL file
lx.io.save_annotated_documents([result], output_name="extraction_resultsV1.jsonl", output_dir=output_dirpath)

# Generate the visualization from the file
html_content = lx.visualize(os.path.join(output_dirpath, "extraction_resultsV1.jsonl"))
with open(os.path.join(output_dirpath, "visualizationV1.html"), "w",encoding="utf-8") as f:
    if hasattr(html_content, 'data'):
        f.write(html_content.data)  # For Jupyter/Colab
    else:
        f.write(html_content)
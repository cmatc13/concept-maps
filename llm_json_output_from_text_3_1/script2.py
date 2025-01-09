from openai import OpenAI
import tiktoken
import logging
from typing import Dict, List, Tuple, Set
from tqdm import tqdm
import json
import time
from datetime import datetime
import os
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConceptRelationshipAnalyzer:
    def __init__(self, api_key: str, checkpoint_dir: str = "checkpoints"):
        self.client = OpenAI(api_key=api_key)
        self.enc = tiktoken.encoding_for_model("gpt-4")
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.last_save_time = time.time()
        self.save_interval = 15 * 60  # 15 minutes in seconds
        
    def save_checkpoint(self, data: Dict, stage: str):
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_file = self.checkpoint_dir / f"checkpoint_{stage}_{timestamp}.json"
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Checkpoint saved: {checkpoint_file}")
            self.last_save_time = current_time

    def load_latest_checkpoint(self, stage: str) -> Dict:
        checkpoints = list(self.checkpoint_dir.glob(f"checkpoint_{stage}_*.json"))
        if not checkpoints:
            return None
        latest_checkpoint = max(checkpoints, key=lambda x: x.stat().st_mtime)
        with open(latest_checkpoint, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Previous methods remain the same until process_content

    def process_content(self, content: str) -> Dict:
        """Process content with checkpointing."""
        # Try to load checkpoint
        result = self.load_latest_checkpoint("final")
        if result:
            logger.info("Resuming from latest checkpoint")
            return result

        batches = self.read_text_in_batches(content)
        
        # Load or initialize concepts and relationships
        checkpoint_data = self.load_latest_checkpoint("initial")
        if checkpoint_data:
            all_concepts = {c["name"]: c["description"] for c in checkpoint_data["concepts"]}
            initial_relationships = checkpoint_data["relationships"]
            processed_batches = checkpoint_data.get("processed_batches", 0)
            batches = batches[processed_batches:]
        else:
            all_concepts = {}
            initial_relationships = []
            processed_batches = 0

        # Extract initial concepts and relationships
        for idx, batch in enumerate(tqdm(batches, desc="Processing initial concepts")):
            concepts, relationships = self.extract_concepts_with_gpt4(batch)
            for concept in concepts:
                all_concepts[concept["name"]] = concept["description"]
            initial_relationships.extend(relationships)
            
            # Save checkpoint
            checkpoint_data = {
                "concepts": [{"name": k, "description": v} for k, v in all_concepts.items()],
                "relationships": initial_relationships,
                "processed_batches": processed_batches + idx + 1
            }
            self.save_checkpoint(checkpoint_data, "initial")

        # Analyze relationships
        logger.info("Analyzing relationships between concepts...")
        
        # Load or perform relationship analysis
        checkpoint_data = self.load_latest_checkpoint("relationships")
        if checkpoint_data and "relationships" in checkpoint_data:
            analyzed_relationships = checkpoint_data["relationships"]
        else:
            analyzed_relationships = self.analyze_relationships(all_concepts)
            self.save_checkpoint({"relationships": analyzed_relationships}, "relationships")

        # Create final result
        result = {
            "concepts": [{"name": k, "description": v} for k, v in all_concepts.items()],
            "relationships": analyzed_relationships
        }
        self.save_checkpoint(result, "final")
        
        return result

def main():
    input_file = "C:/Users/49151/Documents/python/network/ocr_text_2/berkshire_letters2.txt"
    output_file = "C:/Users/49151/Documents/python/network/llm_json_output_from_text_3_1/berkshire_letters.json"
    checkpoint_dir = "checkpoints"
    
    analyzer = ConceptRelationshipAnalyzer(
        api_key=os.getenv("OPENAI_API_KEY"),
        checkpoint_dir=checkpoint_dir
    )
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    result = analyzer.process_content(content)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Analysis complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()
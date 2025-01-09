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
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.enc = tiktoken.encoding_for_model("gpt-4")
        
    def read_text_in_batches(self, content: str) -> List[str]:
        """Split text into optimally-sized overlapping batches."""
        max_tokens = self.calculate_optimal_batch_size()
        overlap_tokens = 200
        tokens = self.enc.encode(content)
        total_tokens = len(tokens)
        
        batches = []
        start_idx = 0

        while start_idx < total_tokens:
            end_idx = min(start_idx + max_tokens, total_tokens)
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self.enc.decode(chunk_tokens)

            if end_idx < total_tokens:
                last_para = chunk_text.rfind('\n\n')
                last_sentence = chunk_text.rfind('. ')
                break_point = last_para if last_para != -1 else last_sentence

                if break_point != -1:
                    chunk_text = chunk_text[:break_point]
                    actual_tokens = len(self.enc.encode(chunk_text))
                    end_idx = start_idx + actual_tokens

            batches.append(chunk_text)
            start_idx = end_idx - overlap_tokens if end_idx < total_tokens else end_idx
        
        return batches

    def calculate_optimal_batch_size(self) -> int:
        """Calculate optimal batch size considering token limits"""
        CONTEXT_WINDOW = 128000
        SYSTEM_PROMPT_TOKENS = len(self.enc.encode("""
            You are a wise and highly intelligent investor. You are the emobidement of Charlie Munger and Warren Buffet. 
            You think deeply about a wide range of topics and can see the relationships betweeen different fields.
            You see the world from a multi-disciplinary perspective and understand that the world is a complex adaptive system.
            You use mental models to navigate the world and can easily see patterns and make informed decisions. 
            For each concept:
            1. Provide a clear description
            2. Identify relationships with other concepts
            3. Assign relationship weights (0.0 to 1.0) based on connection strength
            
            Format as JSON with two lists:
            {
                "concepts": [{"name": "concept_name", "description": "description"}],
                "relationships": [{"source": "concept1", "target": "concept2", "weight": 0.8}]
            }
                                                   
            Focus on substantive concepts and meaningful relationships. Aim to identify roughly 30 key concepts per chunk of text maximum. You are free to choose less or more if they are important or not however less is best.
            Once you have all of the concepts and descriptions. Re-check all of them to ensure they are distinct concepts in meaning and remove any that are essentially the same concept.                                       
            """))
        
        AVAILABLE_TOKENS = CONTEXT_WINDOW - SYSTEM_PROMPT_TOKENS
        return int(AVAILABLE_TOKENS * 0.4)

    def extract_concepts_with_gpt4(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract initial concepts and relationships using GPT-4."""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": """
                            You are a wise and highly intelligent investor. You are the emobidement of Charlie Munger and Warren Buffet. 
                            You think deeply about a wide range of topics and can see the relationships betweeen different fields.
                            You see the world from a multi-disciplinary perspective and understand that the world is a complex adaptive system.
                            You use mental models to navigate the world and can easily see patterns and make informed decisions. 
                            For each concept:
                            1. Provide a clear description
                            2. Identify relationships with other concepts
                            3. Assign relationship weights (0.0 to 1.0) based on connection strength
                            
                            Format as JSON with two lists:
                            {
                                "concepts": [{"name": "concept_name", "description": "description"}],
                                "relationships": [{"source": "concept1", "target": "concept2", "weight": 0.8}]
                            }

                            Focus on substantive concepts and meaningful relationships. Aim to identify roughly 30 key concepts per chunk of text maximum. You are free to choose less or more if they are important or not however less is best.
                            Once you have all of the concepts and descriptions. Re-check all of them to ensure they are distinct concepts in meaning and remove any that are essentially the same concept.
                            """
                        },
                        {
                            "role": "user",
                            "content": text
                        }
                    ],
                    temperature=0.4,
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(response.choices[0].message.content)
                return result["concepts"], result["relationships"]
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Failed to process chunk after {max_retries} attempts: {e}")
                    return [], []

    def analyze_relationships(self, concepts: Dict[str, str]) -> List[Dict]:
        """Analyze relationships between concepts using GPT-4."""
        concept_pairs = []
        concept_names = list(concepts.keys())
        
        # Create unique pairs of concepts
        for i in range(len(concept_names)):
            for j in range(i + 1, len(concept_names)):
                concept_pairs.append((concept_names[i], concept_names[j]))

        # Process concept pairs in batches to stay within token limits
        batch_size = 10
        all_relationships = []

        for i in range(0, len(concept_pairs), batch_size):
            batch_pairs = concept_pairs[i:i + batch_size]
            
            # Create the prompt for relationship analysis
            prompt = "Analyze the relationship between these concept pairs:\n\n"
            for pair in batch_pairs:
                prompt += f"Concept 1: {pair[0]}\nDescription: {concepts[pair[0]]}\n"
                prompt += f"Concept 2: {pair[1]}\nDescription: {concepts[pair[1]]}\n\n"

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": """
                            You are a wise and highly intelligent investor. You are the emobidement of Charlie Munger and Warren Buffet. 
                            You think deeply about a wide range of topics and can see the relationships betweeen different fields.
                            You see the world from a multi-disciplinary perspective and understand that the world is a complex adaptive system.
                            You use mental models to navigate the world and can easily see patterns and make informed decisions. 
                            Analyze the relationships between concept pairs.
                            For each pair:
                            1. Determine if there is a meaningful relationship
                            2. If yes, describe the relationship and assign a weight (0.0 to 1.0)
                            3. If no relationship exists, exclude it from the output

                            Return as JSON:
                            {
                                "relationships": [
                                    {
                                        "source": "concept1",
                                        "target": "concept2",
                                        "weight": 0.8,
                                        "description": "Brief description of relationship"
                                    }
                                ]
                            }
                            """
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.4,
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(response.choices[0].message.content)
                all_relationships.extend(result.get("relationships", []))
                
            except Exception as e:
                logger.error(f"Error processing batch: {e}")
                continue

        return all_relationships

    def process_content(self, content: str) -> Dict:
        """Process content and create concept relationship data structure."""
        batches = self.read_text_in_batches(content)
        
        # Extract initial concepts and relationships
        all_concepts = {}
        initial_relationships = []
        
        for batch in tqdm(batches, desc="Processing initial concepts"):
            concepts, relationships = self.extract_concepts_with_gpt4(batch)
            for concept in concepts:
                all_concepts[concept["name"]] = concept["description"]
            initial_relationships.extend(relationships)

        # Analyze relationships between all concepts
        logger.info("Analyzing relationships between concepts...")
        analyzed_relationships = self.analyze_relationships(all_concepts)
        
        # Create final data structure
        result = {
            "concepts": [{"name": k, "description": v} for k, v in all_concepts.items()],
            "relationships": analyzed_relationships
        }
        
        return result

def main():
    input_file = "C:/Users/49151/Documents/python/network/ocr_text_2/berkshire_letters2.txt"
    output_file = "C:/Users/49151/Documents/python/network/llm_json_output_from_text_3_1/berkshire_letters.json"
    
    analyzer = ConceptRelationshipAnalyzer(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Read content
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Process content
    result = analyzer.process_content(content)
    
    # Save results
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"Analysis complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()
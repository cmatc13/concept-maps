import json
import asyncio
import os
from pathlib import Path
import logging
from typing import List, Dict, Set
from openai import AsyncOpenAI
import time
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, requests_per_minute=20):
        self.requests_per_minute = requests_per_minute
        self.interval = 60 / requests_per_minute
        self.last_request_time = 0
        self.lock = asyncio.Lock()
        self.retry_after = 60

    async def acquire(self):
        async with self.lock:
            now = time.time()
            time_since_last_request = now - self.last_request_time
            if time_since_last_request < self.interval:
                wait_time = self.interval - time_since_last_request
                await asyncio.sleep(wait_time)
            self.last_request_time = time.time()

class CrossBookGraphAnalyzer:
    SYSTEM_PROMPT = """
    You are a wise and highly intelligent investor. You are the embodiment of Charlie Munger and Warren Buffett. 
        You think deeply about a wide range of topics and can see the relationships between different fields.
        You see the world from a multi-disciplinary perspective and understand that the world is a complex adaptive system.
        You use mental models to navigate the world and can easily see patterns and make informed decisions. 
       
    For each pair of concepts:
    1. Determine if there is a meaningful relationship
    2. Assign a relationship weight (0.0 to 1.0) based on connection strength
    3. Provide a brief justification for the relationship
    
    Respond with a JSON list of relationships:
    {
        "relationships": [
            {
                "source": "concept1",
                "target": "concept2",
                "weight": 0.8,
                "type": "cross_book",
                "source_book": "book1",
                "target_book": "book2",
                "justification": "Brief explanation of relationship"
            }
        ]
    }
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.rate_limiter = RateLimiter()

    def load_book_graphs(self, file_paths: List[str]) -> Dict:
        """Load and combine multiple book concept graphs."""
        combined_data = {
            "concepts": [],
            "relationships": [],
            "book_metadata": {}
        }
        
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8') as f:
                book_data = json.load(f)
                # Extract book name from file name
                book_name = Path(file_path).stem
                # Remove common suffixes if present
                book_name = book_name.replace("_graph", "").replace(".json", "")
                
                # Clean up the book name
                book_name = book_name.replace("_", " ").title()
                
                logger.info(f"Processing book: {book_name}")
                
                # Add book metadata
                combined_data["book_metadata"][book_name] = {
                    "concept_count": len(book_data["concepts"]),
                    "relationship_count": len(book_data["relationships"]),
                    "file_path": str(file_path)
                }
                
                # Add source book to concepts
                for concept in book_data["concepts"]:
                    concept["source_book"] = book_name
                    combined_data["concepts"].append(concept)
                
                # Add source book to relationships
                for rel in book_data["relationships"]:
                    rel["source_book"] = book_name
                    rel["target_book"] = book_name
                    rel["type"] = "internal"
                    combined_data["relationships"].append(rel)
                
                logger.info(f"Added {len(book_data['concepts'])} concepts and {len(book_data['relationships'])} relationships from {book_name}")
        
        return combined_data
    
    
    async def _process_concept_batch(self, concept_pairs: List[tuple]) -> List[Dict]:
        """Process a batch of concept pairs to find relationships."""
        prompt = "Analyze these concept pairs and determine if meaningful relationships exist between them:\n\n"
        for c1, c2 in concept_pairs:
            prompt += f"Book 1: {c1['source_book']}\nConcept 1: {c1['name']}\nDescription 1: {c1['description']}\n"
            prompt += f"Book 2: {c2['source_book']}\nConcept 2: {c2['name']}\nDescription 2: {c2['description']}\n\n"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self.rate_limiter.acquire()
                async with AsyncOpenAI(api_key=self.api_key) as client:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",  
                        messages=[
                            {"role": "system", "content": self.SYSTEM_PROMPT + "\nIMPORTANT: Respond with raw JSON only, no markdown formatting."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                    )
                    
                    content = response.choices[0].message.content
                    logger.info(f"Raw response content: {content[:200]}...")  # Log first 200 chars
                    
                    # Clean the response of any markdown formatting
                    cleaned_content = content
                    if content.startswith('```'):
                        cleaned_content = content.split('```')[1]
                        if cleaned_content.startswith('json'):
                            cleaned_content = cleaned_content[4:]
                        cleaned_content = cleaned_content.strip()
                    
                    try:
                        parsed_response = json.loads(cleaned_content)
                        if not isinstance(parsed_response, dict):
                            raise ValueError(f"Response is not a dictionary: {cleaned_content}")
                        if "relationships" not in parsed_response:
                            raise ValueError(f"Response missing relationships key: {cleaned_content}")
                        
                        relationships = parsed_response["relationships"]
                        if not isinstance(relationships, list):
                            raise ValueError(f"Relationships is not a list: {relationships}")
                            
                        # Validate each relationship
                        valid_relationships = []
                        for rel in relationships:
                            if all(key in rel for key in ["source", "target", "weight", "type", "source_book", "target_book", "justification"]):
                                valid_relationships.append(rel)
                            else:
                                logger.warning(f"Skipping invalid relationship: {rel}")
                        
                        logger.info(f"Successfully parsed {len(valid_relationships)} valid relationships")
                        return valid_relationships
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error: {str(e)}")
                        logger.error(f"Attempted to parse content: {cleaned_content[:200]}...")
                        if attempt == max_retries - 1:
                            raise
                        continue

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if "429" in str(e):  # Rate limit error
                    await asyncio.sleep(60)  # Wait longer for rate limit errors
                elif attempt == max_retries - 1:
                    logger.error("Max retries reached, skipping batch")
                    return []
                await asyncio.sleep(2 ** attempt)

        return []



    async def analyze_cross_book_relationships(self, combined_data: Dict) -> List[Dict]:
        """Analyze relationships between concepts from different books."""
        concepts_by_book = {}
        for concept in combined_data["concepts"]:
            book = concept["source_book"]
            if book not in concepts_by_book:
                concepts_by_book[book] = []
            concepts_by_book[book].append(concept)

        def get_key_concepts(concepts, limit=50):
            return sorted(concepts, key=lambda x: len(x['description']), reverse=True)[:limit]

        # Generate pairs of concepts from different books
        concept_pairs = []
        books = list(concepts_by_book.keys())
        for i in range(len(books)):
            for j in range(i + 1, len(books)):
                book1, book2 = books[i], books[j]
                concepts1 = get_key_concepts(concepts_by_book[book1])
                concepts2 = get_key_concepts(concepts_by_book[book2])
                for c1 in concepts1:
                    for c2 in concepts2:
                        concept_pairs.append((c1, c2))

        # Process batches in parallel
        batch_size = 200
        semaphore = asyncio.Semaphore(5)

        async def bounded_process_batch(batch):
            async with semaphore:
                return await self._process_concept_batch(batch)

        batches = [concept_pairs[i:i + batch_size] for i in range(0, len(concept_pairs), batch_size)]
        tasks = [bounded_process_batch(batch) for batch in batches]
        results = await asyncio.gather(*tasks)
        
        cross_book_relationships = []
        for batch_result in results:
            if batch_result:
                cross_book_relationships.extend(batch_result)
                
        return cross_book_relationships


    def merge_relationships(self, combined_data: Dict, cross_book_relationships: List[Dict]) -> Dict:
        """Merge internal and cross-book relationships."""
        # Add cross-book relationships to the combined data
        combined_data["relationships"].extend(cross_book_relationships)
        
        # Add statistics
        combined_data["statistics"] = {
            "total_concepts": len(combined_data["concepts"]),
            "internal_relationships": len([r for r in combined_data["relationships"] if r["type"] == "internal"]),
            "cross_book_relationships": len(cross_book_relationships),
            "books_analyzed": len(combined_data["book_metadata"])
        }
        
        return combined_data

async def main():
    # Configuration
    input_directory = "C:/Users/49151/Documents/python/network/llm_json_output_from_text_3_1"
    output_file = "C:/Users/49151/Documents/python/network/multi_graph_network/combined_analysis.json"
    api_key = os.getenv("OPENAI_API_KEY")

    # Initialize analyzer
    analyzer = CrossBookGraphAnalyzer(api_key)

    try:
        # Get all JSON files in the input directory
        json_files = list(Path(input_directory).glob("*.json"))
        
        # Load and combine book graphs
        combined_data = analyzer.load_book_graphs([str(f) for f in json_files])
        logger.info(f"Loaded {len(json_files)} books with {len(combined_data['concepts'])} total concepts")

        # Analyze cross-book relationships
        cross_book_relationships = await analyzer.analyze_cross_book_relationships(combined_data)
        logger.info(f"Found {len(cross_book_relationships)} cross-book relationships")

        # Merge all relationships
        final_result = analyzer.merge_relationships(combined_data, cross_book_relationships)

        # Save results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Analysis complete. Results saved to {output_file}")

    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
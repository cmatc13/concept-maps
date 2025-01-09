from openai import OpenAI, AsyncOpenAI
import tiktoken
import logging
from typing import Dict, List, Tuple, Set
from tqdm import tqdm
import json
import time
from datetime import datetime
import os
from pathlib import Path
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, requests_per_minute=3):  # Reduced from 40 to 3
        self.requests_per_minute = requests_per_minute
        self.interval = 60 / requests_per_minute
        self.last_request_time = 0
        self.lock = asyncio.Lock()
        self.retry_after = 60  # Default 60 second cooldown after rate limit

    async def acquire(self):
        async with self.lock:
            now = time.time()
            time_since_last_request = now - self.last_request_time
            if time_since_last_request < self.interval:
                wait_time = self.interval - time_since_last_request
                await asyncio.sleep(wait_time)
            self.last_request_time = time.time()

    async def handle_rate_limit(self):
        """Handle rate limit by implementing a cooldown period"""
        async with self.lock:
            logger.info(f"Rate limit hit. Cooling down for {self.retry_after} seconds")
            await asyncio.sleep(self.retry_after)
            self.retry_after *= 2  # Double the cooldown period for next time

async def process_single_batch(self, batch: str):
    max_retries = 5
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            await self.rate_limiter.acquire()
            async with AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) as client:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": batch}
                    ],
                    temperature=0.3,
                )
                
                content = response.choices[0].message.content
                logger.info(f"Raw response content: {content[:200]}...")  # Log first 200 chars
                
                # Add better error handling for JSON parsing
                try:
                    parsed_response = json.loads(content)
                    if not isinstance(parsed_response, dict):
                        raise ValueError(f"Response is not a dictionary: {content}")
                    if "concepts" not in parsed_response or "relationships" not in parsed_response:
                        raise ValueError(f"Response missing required keys: {content}")
                    if not parsed_response["concepts"]:  # Check if concepts list is empty
                        raise ValueError(f"No concepts found in response: {content}")
                    return parsed_response
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Error parsing response: {str(e)}")
                    if attempt == max_retries - 1:
                        raise  # Re-raise on final attempt
                    continue  # Try again if we have attempts left
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed with error: {str(e)}")
            if "429" in str(e):  # Rate limit error
                await self.rate_limiter.handle_rate_limit()
            elif attempt == max_retries - 1:
                logger.error(f"Final error processing batch after {max_retries} attempts: {str(e)}")
                return None
            
            delay = (base_delay * 2 ** attempt) + (random.random() * 0.1)
            logger.info(f"Retrying in {delay:.2f} seconds...")
            await asyncio.sleep(delay)
    
    return None

async def process_content(self, content: str) -> Dict:
    """Process content with improved error handling and data saving"""
    result = self.load_latest_checkpoint("final")
    if result:
        return result

    batches = self.read_text_in_batches(content)
    logger.info(f"Processing {len(batches)} batches")
    
    # Process batches
    all_results = await self.extract_concepts_batch(batches)
    
    # Combine results with better error handling
    all_concepts = {}
    initial_relationships = []
    
    for result in all_results:
        if result and isinstance(result, dict):
            # Log the processing of each result
            logger.info(f"Processing result with {len(result.get('concepts', []))} concepts")
            
            for concept in result.get("concepts", []):
                if isinstance(concept, dict) and "name" in concept and "description" in concept:
                    all_concepts[concept["name"]] = concept["description"]
            
            relationships = result.get("relationships", [])
            if isinstance(relationships, list):
                initial_relationships.extend(relationships)

    logger.info(f"Total concepts gathered: {len(all_concepts)}")
    logger.info(f"Total initial relationships: {len(initial_relationships)}")

    # Create final result
    final_result = {
        "concepts": [{"name": k, "description": v} for k, v in all_concepts.items()],
        "relationships": initial_relationships
    }

    # Save checkpoint before returning
    self.save_checkpoint(final_result, "final")
    
    # Verify the result is valid JSON before returning
    try:
        # Test serialization
        json.dumps(final_result)
        return final_result
    except Exception as e:
        logger.error(f"Error serializing final result: {e}")
        return {"concepts": [], "relationships": []}

class OptimizedConceptRelationshipAnalyzer:
    SYSTEM_PROMPT = """
        You are a wise and highly intelligent investor. You are the embodiment of Charlie Munger and Warren Buffett. 
        You think deeply about a wide range of topics and can see the relationships between different fields.
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
        
        Focus on substantive concepts and meaningful relationships. Aim to identify roughly 30 key concepts per chunk of text maximum.
        Once you have all of the concepts and descriptions, re-check all of them to ensure they are distinct concepts in meaning.
    """

    def __init__(self, api_key: str, checkpoint_dir: str = "checkpoints"):
        self.client = OpenAI(api_key=api_key)
        self.enc = tiktoken.encoding_for_model("gpt-4o-mini")
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.last_save_time = time.time()
        self.save_interval = 15 * 60  # 15 minutes
        self.max_concurrent_requests = 1
        self.rate_limiter = RateLimiter(requests_per_minute=3)

    def calculate_optimal_batch_size(self) -> int:
        """Calculate optimal batch size based on context window"""
        CONTEXT_WINDOW = 128000
        SYSTEM_PROMPT_TOKENS = len(self.enc.encode(self.SYSTEM_PROMPT))
        AVAILABLE_TOKENS = CONTEXT_WINDOW - SYSTEM_PROMPT_TOKENS
        return int(AVAILABLE_TOKENS * 0.4)

    def read_text_in_batches(self, content: str) -> List[str]:
        """Split content into optimal sized batches with overlap"""
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

    async def process_single_batch(self, batch: str):
        """Process a single batch of text"""
        max_retries = 5
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                await self.rate_limiter.acquire()
                async with AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) as client:
                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": self.SYSTEM_PROMPT + "\nIMPORTANT: Respond with raw JSON only, no markdown formatting."},
                            {"role": "user", "content": batch}
                        ],
                        temperature=0.3,
                    )
                    
                    content = response.choices[0].message.content
                    logger.info(f"Raw response content: {content[:200]}...")
                    
                    # Clean the response of any markdown formatting
                    cleaned_content = content
                    if content.startswith('```'):
                        # Remove the opening ``` and closing ```
                        cleaned_content = content.split('```')[1]
                        # If it starts with 'json', remove that too
                        if cleaned_content.startswith('json'):
                            cleaned_content = cleaned_content[4:]
                        cleaned_content = cleaned_content.strip()
                    
                    try:
                        parsed_response = json.loads(cleaned_content)
                        if not isinstance(parsed_response, dict):
                            raise ValueError(f"Response is not a dictionary: {cleaned_content}")
                        if "concepts" not in parsed_response or "relationships" not in parsed_response:
                            raise ValueError(f"Response missing required keys: {cleaned_content}")
                        if not parsed_response["concepts"]:
                            raise ValueError(f"No concepts found in response: {cleaned_content}")
                        logger.info(f"Successfully parsed response with {len(parsed_response['concepts'])} concepts")
                        return parsed_response
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error(f"Error parsing response: {str(e)}")
                        logger.error(f"Attempted to parse content: {cleaned_content[:200]}...")
                        if attempt == max_retries - 1:
                            raise
                        continue
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with error: {str(e)}")
                if "429" in str(e):  # Rate limit error
                    await self.rate_limiter.handle_rate_limit()
                elif attempt == max_retries - 1:
                    logger.error(f"Final error processing batch after {max_retries} attempts: {str(e)}")
                    return None
                
                delay = (base_delay * 2 ** attempt) + (random.random() * 0.1)
                logger.info(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
        
        return None
    

    async def extract_concepts_batch(self, batches: List[str]) -> List[Dict]:
        """Extract concepts from multiple batches"""
        results = []
        for i in range(0, len(batches), self.max_concurrent_requests):
            batch_group = batches[i:i + self.max_concurrent_requests]
            tasks = [self.process_single_batch(batch) for batch in batch_group]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed with error: {str(result)}")
                    continue
                if result is not None:
                    results.append(result)
            
            if i + self.max_concurrent_requests < len(batches):
                await asyncio.sleep(2)
        
        if not results:
            logger.error("No valid results were obtained from any batch")
            raise ValueError("Failed to extract any concepts from the content")
            
        return results

    async def analyze_relationships_async(self, concepts: Dict[str, str]) -> List[Dict]:
        """Analyze relationships between concepts"""
        concept_pairs = [(c1, c2) for i, c1 in enumerate(concepts.keys()) 
                        for c2 in list(concepts.keys())[i+1:]]
        
        batch_size = 10
        relationship_batches = [concept_pairs[i:i + batch_size] 
                              for i in range(0, len(concept_pairs), batch_size)]
        
        async def process_batch(batch):
            pairs_text = "\n".join([f"{c1} - {c2}" for c1, c2 in batch])
            max_retries = 5
            base_delay = 1
            
            for attempt in range(max_retries):
                try:
                    await self.rate_limiter.acquire()
                    async with AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) as client:
                        response = await client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "Analyze relationships between concept pairs."},
                                {"role": "user", "content": f"Analyze these concept pairs:\n{pairs_text}"}
                            ],
                            temperature=0.3,
                        )
                        return json.loads(response.choices[0].message.content)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Error analyzing relationships: {e}")
                        return []
                    delay = (base_delay * 2 ** attempt) + (random.random() * 0.1)
                    await asyncio.sleep(delay)

        relationships = []
        for i in range(0, len(relationship_batches), self.max_concurrent_requests):
            batch_group = relationship_batches[i:i + self.max_concurrent_requests]
            tasks = [process_batch(batch) for batch in batch_group]
            results = await asyncio.gather(*tasks)
            for result in results:
                if result:
                    relationships.extend(result)
            
            if i + self.max_concurrent_requests < len(relationship_batches):
                await asyncio.sleep(2)
                
        return relationships

    def save_checkpoint(self, data: Dict, stage: str):
        """Save checkpoint to file"""
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            checkpoint_file = self.checkpoint_dir / f"checkpoint_{stage}_{timestamp}.json"
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Checkpoint saved: {checkpoint_file}")
            self.last_save_time = current_time

    def load_latest_checkpoint(self, stage: str) -> Dict:
        """Load the latest checkpoint for a given stage"""
        checkpoints = list(self.checkpoint_dir.glob(f"checkpoint_{stage}_*.json"))
        if not checkpoints:
            return None
        latest_checkpoint = max(checkpoints, key=lambda x: x.stat().st_mtime)
        with open(latest_checkpoint, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def process_content(self, content: str) -> Dict:
        """Process content and generate concepts and relationships"""
        result = self.load_latest_checkpoint("final")
        if result:
            return result

        try:
            batches = self.read_text_in_batches(content)
            logger.info(f"Processing {len(batches)} batches")
            
            all_results = await self.extract_concepts_batch(batches)
            
            all_concepts = {}
            initial_relationships = []
            
            for result in all_results:
                if result and isinstance(result, dict):
                    logger.info(f"Processing result with {len(result.get('concepts', []))} concepts")
                    
                    for concept in result.get("concepts", []):
                        if isinstance(concept, dict) and "name" in concept and "description" in concept:
                            all_concepts[concept["name"]] = concept["description"]
                    
                    relationships = result.get("relationships", [])
                    if isinstance(relationships, list):
                        initial_relationships.extend(relationships)

            if not all_concepts:
                raise ValueError("No valid concepts were extracted from any batch")

            logger.info(f"Total concepts gathered: {len(all_concepts)}")
            logger.info(f"Total initial relationships: {len(initial_relationships)}")

            final_result = {
                "concepts": [{"name": k, "description": v} for k, v in all_concepts.items()],
                "relationships": initial_relationships
            }

            self.save_checkpoint(final_result, "final")
            
            try:
                json.dumps(final_result)  # Verify JSON serialization
                return final_result
            except Exception as e:
                logger.error(f"Error serializing final result: {e}")
                raise
                
        except Exception as e:
            logger.error(f"Error in process_content: {str(e)}")
            raise

async def main():
    input_file = "C:/Users/49151/Documents/python/network/ocr_text_2/principles_dalio.txt"
    output_file = "C:/Users/49151/Documents/python/network/llm_json_output_from_text_3_1/principles_dalio.json"
    checkpoint_dir = "C:/Users/49151/Documents/python/network/llm_json_output_from_text_3_1/checkpoints_principles_dalio"
    
    analyzer = OptimizedConceptRelationshipAnalyzer(
        api_key=os.getenv("OPENAI_API_KEY"),
        checkpoint_dir=checkpoint_dir
    )
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        result = await analyzer.process_content(content)
        
        # Verify result is not empty
        if not result or not result.get("concepts"):
            logger.error("No concepts were generated!")
            return
            
        # Pretty print JSON for better readability
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        logger.info(f"Analysis complete. Results saved to {output_file}")
        logger.info(f"Generated {len(result['concepts'])} concepts and {len(result['relationships'])} relationships")
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise
    
    logger.info(f"Analysis complete. Results saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
from openai import OpenAI
import networkx as nx
from pathlib import Path
import logging
from collections import defaultdict
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tiktoken
from tqdm import tqdm
import os 



api_key=os.getenv("OPENAI_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BookConceptProcessor:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        self.graphs = {}  # Store multiple graphs
        self.enc = tiktoken.encoding_for_model("gpt-4o-mini")

    def calculate_optimal_batch_size(self) -> int:
        """Calculate optimal batch size considering token limits"""
        CONTEXT_WINDOW = 128000
        SYSTEM_PROMPT_TOKENS = len(self.enc.encode("""
            You are a wise and highly intelligent investor. You are the emobidement of Charlie Munger and Warren Buffet. 
            You think deeply about a wide range of topics and can see the relationships betweeen different fields.
            You see the world from a multi-disciplinary perspective and understand that the world is a complex adaptive system.
            You use mental models to navigate the world and can easily see patterns and make informed decisions. 
            Your task is to extract key concepts, ideas, mental models as they relate to life and investing and their relationships from the text. For each concept:
            1. Provide a clear, one-sentence description
            2. Identify relationships with other concepts
            3. Assign relationship weights (0.0 to 1.0) based on strength of connection
            
            Format the response as JSON with two lists:
            {
                "concepts": [{"name": "concept_name", "description": "one sentence description"}],
                "relationships": [{"source": "concept1", "target": "concept2", "weight": 0.8}]
            }
            
            Focus on substantive concepts and meaningful relationships. Aim to identify roughly 30 key concepts per chunk of text maximum. You are free to choose less or more if they are important or not however less is best.
            Once you have all of the concepts and descriptions. Re-check all of them to ensure they are distinct concepts in meaning and remove any that are essentially the same concept.
            """))
        
        # Reserve 60% of remaining tokens for output (concepts and relationships)
        AVAILABLE_TOKENS = CONTEXT_WINDOW - SYSTEM_PROMPT_TOKENS
        INPUT_TOKENS = int(AVAILABLE_TOKENS * 0.4)  # 40% for input
        
        return INPUT_TOKENS

    def read_text_in_batches(self, content: str) -> List[str]:
        """Split text into optimally-sized overlapping batches."""
        max_tokens = self.calculate_optimal_batch_size()
        overlap_tokens = 200  # Number of overlapping tokens between batches
        tokens = self.enc.encode(content)
        total_tokens = len(tokens)
        
        batches = []
        start_idx = 0

        while start_idx < total_tokens:
            end_idx = min(start_idx + max_tokens, total_tokens)
            chunk_tokens = tokens[start_idx:end_idx]
            chunk_text = self.enc.decode(chunk_tokens)

            # Find a good break point (end of paragraph or sentence)
            if end_idx < total_tokens:
                last_para = chunk_text.rfind('\n\n')
                last_sentence = chunk_text.rfind('. ')
                break_point = last_para if last_para != -1 else last_sentence

                if break_point != -1:
                    chunk_text = chunk_text[:break_point]
                    actual_tokens = len(self.enc.encode(chunk_text))
                    end_idx = start_idx + actual_tokens

            batches.append(chunk_text)

            # Move the start index forward, keeping the overlap
            start_idx = end_idx - overlap_tokens if end_idx < total_tokens else end_idx
        
        logger.info(f"Split text into {len(batches)} overlapping batches of approximately {max_tokens} tokens each")
        return batches


    def extract_concepts_with_gpt4(self, text: str) -> Tuple[List[Dict], List[Dict]]:
        """Extract concepts and relationships using GPT-4."""
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
                            Your task is to extract key concepts, ideas, mental models as they relate to life and investing and their relationships from the text. For each concept:
                            1. Provide a clear, one-sentence description
                            2. Identify relationships with other concepts
                            3. Assign relationship weights (0.0 to 1.0) based on strength of connection
                            
                            Format the response as JSON with two lists:
                            {
                                "concepts": [{"name": "concept_name", "description": "one sentence description"}],
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
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to process chunk after {max_retries} attempts: {e}")
                    return [], []

    def process_book(self, title: str, content: str) -> nx.DiGraph:
        """Process a single book and create its concept graph."""
        graph = nx.DiGraph()
        
        # Add book metadata to graph
        graph.graph['title'] = title
        graph.graph['processed_date'] = datetime.now().isoformat()
        
        # Process content in batches
        batches = self.read_text_in_batches(content)
        all_concepts = []
        all_relationships = []
        
        # Process batches with progress bar
        for batch in tqdm(batches, desc=f"Processing {title} batches"):
            concepts, relationships = self.extract_concepts_with_gpt4(batch)
            all_concepts.extend(concepts)
            all_relationships.extend(relationships)

        # Deduplicate concepts while preserving best descriptions
        concept_map = {}
        for concept in all_concepts:
            name = concept["name"].lower()  # Normalize names
            if name not in concept_map or len(concept["description"]) > len(concept_map[name]["description"]):
                concept_map[name] = concept
        
        # Add nodes with enhanced attributes
        for concept in concept_map.values():
            graph.add_node(
                concept["name"],
                description=concept["description"],
                type=concept.get("type", "concept"),
                importance=concept.get("importance", 0.5),
                chapter=concept.get("chapter", "unknown"),
                book_title=title
            )
        
        # Combine relationships and average weights for duplicates
        relationship_map = defaultdict(list)
        for rel in all_relationships:
            source = rel["source"].lower()
            target = rel["target"].lower()
            relationship_map[(source, target)].append(rel["weight"])
        
        # Add edges with averaged weights
        for (source, target), weights in relationship_map.items():
            if source in concept_map and target in concept_map:
                avg_weight = sum(weights) / len(weights)
                graph.add_edge(
                    concept_map[source]["name"],
                    concept_map[target]["name"],
                    weight=avg_weight,
                    relationship_type="related",
                    description=""
                )
        
        self.graphs[title] = graph
        return graph

    def merge_graphs(self, book_titles: Optional[List[str]] = None) -> nx.DiGraph:
        """
        Merge multiple book graphs into one, with enhanced cross-book relationships.
        
        Args:
            book_titles: List of book titles to merge. If None, merges all.
        """
        if book_titles is None:
            book_titles = list(self.graphs.keys())
        
        merged = nx.DiGraph()
        
        # Add all nodes and edges from individual books
        for title in book_titles:
            graph = self.graphs[title]
            
            # Add nodes with source book information
            for node, data in graph.nodes(data=True):
                if node not in merged:
                    merged.add_node(node, **data)
                    merged.nodes[node]['books'] = set([title])
                else:
                    merged.nodes[node]['books'].add(title)
                    # Update importance if it appears in multiple books
                    merged.nodes[node]['importance'] = min(
                        1.0, 
                        merged.nodes[node].get('importance', 0.5) + 0.1
                    )
            
            # Add edges
            for source, target, data in graph.edges(data=True):
                if not merged.has_edge(source, target):
                    merged.add_edge(source, target, **data)
                    merged.edges[source, target]['books'] = set([title])
                else:
                    merged.edges[source, target]['books'].add(title)
                    # Strengthen relationship if it appears in multiple books
                    current_weight = merged.edges[source, target]['weight']
                    merged.edges[source, target]['weight'] = min(1.0, current_weight + 0.1)
        
        return merged

    def save_graphml_with_metadata(self, graph: nx.DiGraph, output_path: str):
        """Save graph with enhanced metadata for Cytoscape."""
        # Create a copy of the graph to modify
        save_graph = graph.copy()

        # Add visual style hints and validate attributes for nodes
        for node in save_graph.nodes():
            # Calculate node size based on importance
            importance = save_graph.nodes[node].get('importance', 0.5)
            save_graph.nodes[node]['size'] = 30 + (importance * 30)

            # Convert 'books' attribute to a supported type
            books = save_graph.nodes[node].get('books', set())
            if isinstance(books, (set, list)):
                save_graph.nodes[node]['books'] = ','.join(sorted(map(str, books)))
            else:
                save_graph.nodes[node]['books'] = str(books)

            # Add fallback for any other unsupported types
            for key, value in save_graph.nodes[node].items():
                if not isinstance(value, (int, float, str)):
                    save_graph.nodes[node][key] = str(value)

        # Add visual style hints and validate attributes for edges
        for source, target in save_graph.edges():
            # Calculate edge width based on weight
            weight = save_graph.edges[source, target].get('weight', 0.0)
            save_graph.edges[source, target]['width'] = 1 + (weight * 4)

            # Convert 'books' attribute to a supported type
            books = save_graph.edges[source, target].get('books', set())
            if isinstance(books, (set, list)):
                save_graph.edges[source, target]['books'] = ','.join(sorted(map(str, books)))
            else:
                save_graph.edges[source, target]['books'] = str(books)

            # Add fallback for any other unsupported types
            for key, value in save_graph.edges[source, target].items():
                if not isinstance(value, (int, float, str)):
                    save_graph.edges[source, target][key] = str(value)

        # Save the graph
        try:
            nx.write_graphml(save_graph, output_path)
            logger.info(f"Graph saved successfully to {output_path}")
        except Exception as e:
            logger.error(f"Error saving graph: {e}")
        raise



def read_book_content(file_path: str) -> str:
    """Read content from a book text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise


def main():
    input_file = "C:/Users/49151/Documents/python/network/ocr_text_2/berkshire_letters.txt"  # Path to the text file with 749,189 tokens
    output_dir = "C:/Users/49151/Documents/python/network/graphs_from_text_3/"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    processor = BookConceptProcessor(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Read large text file content
    content = read_book_content(input_file)
    
    # Process the large text in batches with overlap
    title = "Large Text Analysis"
    batches = processor.read_text_in_batches(content)
    graph = nx.DiGraph()
    graph.graph['title'] = title
    graph.graph['processed_date'] = datetime.now().isoformat()

    # Process and save each batch
    for idx, batch in enumerate(tqdm(batches, desc="Processing batches")):
        logger.info(f"Processing batch {idx + 1}/{len(batches)}...")
        
        concepts, relationships = processor.extract_concepts_with_gpt4(batch)
        
        # Add concepts and relationships to the graph
        for concept in concepts:
            graph.add_node(concept["name"], **concept)
        for rel in relationships:
            source = rel["source"]
            target = rel["target"]
            if not graph.has_edge(source, target):
                graph.add_edge(source, target, weight=rel["weight"])
        
        # Save intermediate graph for safety
        intermediate_path = Path(output_dir) / f"graph_batch_{idx + 1}.graphml"
        processor.save_graphml_with_metadata(graph, str(intermediate_path))
        logger.info(f"Saved intermediate graph for batch {idx + 1} to {intermediate_path}")
    
    # Save the final graph
    final_path = Path(output_dir) / "berkshire_letters2.graphml"
    processor.save_graphml_with_metadata(graph, str(final_path))
    logger.info(f"Final graph saved successfully to {final_path}")


if __name__ == "__main__":
    main()
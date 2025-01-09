import networkx as nx
import logging
import matplotlib.pyplot as plt
import os
from collections import defaultdict
import numpy as np
import openai

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def get_embeddings(openai_api_key: str, texts: list) -> list:
    """Fetch embeddings for node descriptions using OpenAI."""
    try:
        openai.api_key = openai_api_key
        embeddings = []
        for text in texts:
            response = openai.embeddings.create(
                    model="text-embedding-3-large",
                    input=text
                )
            embeddings.append(response.data[0].embedding)
        return embeddings
    except Exception as e:
        logger.error(f"Error fetching embeddings: {e}")
        raise

def compute_similarities(embeddings: list, node_ids: list, threshold: float) -> dict:
    """Compute cosine similarity between node embeddings."""
    similarities = defaultdict(list)
    vectors = np.array(embeddings)
    vectors = vectors / np.linalg.norm(vectors, axis=1)[:, None]
    similarity_matrix = np.dot(vectors, vectors.T)

    for i, node_id in enumerate(node_ids):
        for j, sim_score in enumerate(similarity_matrix[i]):
            if i != j and sim_score >= threshold:
                similarities[node_id].append((node_ids[j], sim_score))
    return similarities

def normalize_edge_weight(similarity_score: float, threshold: float, min_width: float = 0.5, max_width: float = 5.0) -> float:
    """Normalize similarity score to edge weight."""
    normalized = (similarity_score - threshold) / (1 - threshold)
    return min_width + normalized * (max_width - min_width)

def visualize_graph(graph: nx.Graph, output_path: str = None):
    """Visualize graph with added edges."""
    pos = nx.spring_layout(graph)
    plt.figure(figsize=(12, 12))
    nx.draw(
        graph, pos, with_labels=True,
        node_size=500, edge_color="blue", font_size=8,
        width=[d['weight'] for _, _, d in graph.edges(data=True)]
    )
    plt.title("Graph Visualization")
    if output_path:
        plt.savefig(output_path)
    plt.show()

def process_single_graph(graph_path: str, output_path: str, openai_api_key: str, similarity_threshold: float = 0.7):
    """Process a single graph by adding edges based on node description similarity."""
    try:
        # Load the graph
        logger.info(f"Loading graph from {graph_path}")
        graph = nx.read_graphml(graph_path)

        # Extract node descriptions
        nodes = {}
        descriptions = []
        node_ids = []

        for node, data in graph.nodes(data=True):
            nodes[node] = data
            descriptions.append(data.get('description', 'No description available'))
            node_ids.append(node)

        logger.info(f"Collected {len(descriptions)} descriptions.")

        # Fetch embeddings
        logger.info("Fetching embeddings for node descriptions.")
        embeddings = get_embeddings(openai_api_key, descriptions)

        # Compute similarities
        logger.info("Computing similarities between nodes.")
        similarities = compute_similarities(embeddings, node_ids, similarity_threshold)

        # Add edges based on similarity
        logger.info("Adding edges based on similarity.")
        for node_id, similar_nodes in similarities.items():
            for similar_node_id, sim_score in similar_nodes:
                edge_width = normalize_edge_weight(sim_score, similarity_threshold)
                graph.add_edge(
                    node_id, similar_node_id,
                    weight=edge_width,
                    similarity=sim_score
                )

        # Save the modified graph
        logger.info(f"Saving updated graph to {output_path}")
        nx.write_graphml(graph, output_path)
        logger.info(f"Graph processing completed successfully. Saved to {output_path}")

    except Exception as e:
        logger.error(f"Error processing graph: {e}")
        raise

if __name__ == "__main__":
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    graph_input_path = "C:/Users/49151/Documents/python/network/graphs_from_text_3/graph_batch_12_corrected.graphml"  # Replace with your input file path
    graph_output_path = "berkshire_letters_embedded.graphml"  # Replace with your desired output file path
    similarity_threshold = 0.7  # Adjust similarity threshold if needed

    if not OPENAI_API_KEY:
        raise ValueError("OpenAI API key not found. Set the OPENAI_API_KEY environment variable.")
    
    process_single_graph(graph_input_path, graph_output_path, OPENAI_API_KEY, similarity_threshold)

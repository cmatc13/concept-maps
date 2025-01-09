import networkx as nx
import numpy as np
from openai import OpenAI
from collections import defaultdict
import os
from typing import Dict, List, Tuple
import logging
import matplotlib.pyplot as plt

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConceptGraphMerger:
    def __init__(self, openai_api_key: str, 
                 min_similarity_threshold: float = 0.5, 
                 edge_width_range: Tuple[float, float] = (0.5, 5.0)):
        try:
            self.client = OpenAI(api_key=openai_api_key)
            self.min_similarity_threshold = min_similarity_threshold
            self.min_edge_width, self.max_edge_width = edge_width_range
            logger.info("ConceptGraphMerger initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing ConceptGraphMerger: {e}")
            raise

    def merge_graphs(self, graph1_path: str, graph2_path: str) -> nx.Graph:
        """Merge two graphs based on node description similarity."""
        try:
            logger.info(f"Loading graph1 from {graph1_path}")
            g1 = nx.read_graphml(graph1_path)

            logger.info(f"Loading graph2 from {graph2_path}")
            g2 = nx.read_graphml(graph2_path)
            
            logger.info("Extracting nodes and descriptions from both graphs.")
            nodes = {}
            descriptions = []
            node_ids = []

            for g in [g1, g2]:
                for node, data in g.nodes(data=True):
                    nodes[node] = data
                    descriptions.append(data.get('description', ''))
                    node_ids.append(node)
            
            logger.info(f"Collected {len(descriptions)} descriptions.")
            
            # Fetch embeddings
            logger.info("Fetching embeddings for node descriptions.")
            embeddings = self.get_embeddings(descriptions)
            
            # Compute similarities
            logger.info("Computing similarities between nodes.")
            similarities = self.compute_similarities(embeddings, node_ids)
            
            # Create merged graph
            logger.info("Creating merged graph based on similarities.")
            merged_graph = self.create_merged_graph(nodes, similarities)

            return merged_graph
        except Exception as e:
            logger.error(f"Error in merge_graphs: {e}")
            raise

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using OpenAI API."""
        try:
            embeddings = []
            for text in texts:
                logger.info(f"Fetching embedding for: {text}")
                response = self.client.embeddings.create(
                    model="text-embedding-3-large",
                    input=text
                )
                embeddings.append(response.data[0].embedding)
            return embeddings
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            raise

    def compute_similarities(self, embeddings: List[List[float]], 
                             node_ids: List[str]) -> Dict[str, List[Tuple[str, float]]]:
        """Compute cosine similarities between embeddings."""
        try:
            similarities = defaultdict(list)
            vectors = np.array(embeddings)
            vectors = vectors / np.linalg.norm(vectors, axis=1)[:, np.newaxis]
            similarity_matrix = np.dot(vectors, vectors.T)

            for i, node_id in enumerate(node_ids):
                sims = [
                    (node_ids[j], similarity_matrix[i][j]) 
                    for j in range(len(node_ids)) if i != j
                ]
                sims.sort(key=lambda x: x[1], reverse=True)
                similarities[node_id] = sims
            return similarities
        except Exception as e:
            logger.error(f"Error computing similarities: {e}")
            raise

    def create_merged_graph(self, nodes: Dict[str, Dict], 
                            similarities: Dict[str, List[Tuple[str, float]]]) -> nx.Graph:
        """Create a merged graph."""
        try:
            G = nx.Graph()

            for node_id, node_data in nodes.items():
                G.add_node(node_id, **node_data)

            edges_added = 0
            for node_id, similar_nodes in similarities.items():
                for similar_node_id, sim_score in similar_nodes:
                    if sim_score >= self.min_similarity_threshold:
                        edge_width = self.normalize_edge_weight(sim_score)
                        G.add_edge(
                            node_id, similar_node_id,
                            weight=edge_width,
                            similarity=sim_score
                        )
                        edges_added += 1

            logger.info(f"Created graph with {len(G.nodes)} nodes and {edges_added} edges.")
            return G
        except Exception as e:
            logger.error(f"Error creating merged graph: {e}")
            raise

    def normalize_edge_weight(self, similarity_score: float) -> float:
        """Normalize edge weight."""
        normalized = ((similarity_score - self.min_similarity_threshold) / 
                     (1 - self.min_similarity_threshold))
        return self.min_edge_width + normalized * (self.max_edge_width - self.min_edge_width)

def save_merged_graph(graph: nx.Graph, output_path: str):
    """Save graph to a GraphML file."""
    try:
        nx.write_graphml(graph, output_path)
        logger.info(f"Graph saved to {output_path}")
    except Exception as e:
        logger.error(f"Error saving graph: {e}")

def visualize_graph(graph: nx.Graph, output_path: str = None):
    """Visualize graph."""
    try:
        pos = nx.spring_layout(graph, k=0.5)
        edge_weights = [d['weight'] for _, _, d in graph.edges(data=True)]

        plt.figure(figsize=(12, 12))
        nx.draw(graph, pos, with_labels=True, width=edge_weights, node_size=500)
        plt.title("Merged Graph Visualization")
        if output_path:
            plt.savefig(output_path)
            logger.info(f"Graph visualization saved to {output_path}")
        plt.show()
    except Exception as e:
        logger.error(f"Error visualizing graph: {e}")

def main():
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY environment variable not set")
        return

    graph1_path = "C:/Users/49151/Documents/python/network/graphs_from_text_3/graph_batch_12_corrected.graphml"
    graph2_path = "C:/Users/49151/Documents/python/network/graphs_from_text_3/graph_batch_12_corrected.graphml"  # You should specify a different second graph
    output_path = "C:/Users/49151/Documents/python/network/graphs_from_text_3/merged_concepts_berkshire_letters2.graphml"
    viz_output_path = "C:/Users/49151/Documents/python/network/graphs_from_text_3/graph_visualization.png"

    try:
        # Initialize the merger
        merger = ConceptGraphMerger(
            openai_api_key=OPENAI_API_KEY,
            min_similarity_threshold=0.5,
            edge_width_range=(0.5, 5.0)
        )

        # Merge the graphs
        merged_graph = merger.merge_graphs(graph1_path, graph2_path)

        # Save the merged graph
        logger.info(f"Saving merged graph to {output_path}")
        save_merged_graph(merged_graph, output_path)

        # Visualize the merged graph
        logger.info(f"Creating visualization at {viz_output_path}")
        visualize_graph(merged_graph, viz_output_path)

        logger.info("Process completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        raise

if __name__ == "__main__":
    main()












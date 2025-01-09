import json
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict

def load_and_create_graph(filepath):
    with open(filepath) as f:
        data = json.load(f)
    
    G = nx.Graph()
    
    # Add concepts as nodes
    for concept in data['concepts']:
        G.add_node(concept['name'], **concept)
    
    # Add relationships with justifications
    for rel in data['relationships']:
        attrs = {
            'weight': rel['weight'],
            'type': rel['type'],
            'source_book': rel['source_book'],
            'target_book': rel['target_book']
        }
        if 'justification' in rel:
            attrs['justification'] = rel['justification']
        
        G.add_edge(rel['source'], rel['target'], **attrs)
    
    return G

def analyze_graph(G):
    # Basic metrics
    analysis = {
        'num_nodes': G.number_of_nodes(),
        'num_edges': G.number_of_edges(),
        'density': nx.density(G),
        'centrality': nx.degree_centrality(G),
    }
    
    # Analyze cross-book relationships
    cross_book_edges = [(u, v, d) for u, v, d in G.edges(data=True) 
                       if d.get('type') == 'cross_book']
    
    # Analyze justifications
    justified_edges = [(u, v, d) for u, v, d in G.edges(data=True) 
                      if 'justification' in d]
    
    analysis['cross_book_count'] = len(cross_book_edges)
    analysis['justified_edges_count'] = len(justified_edges)
    
    return analysis

def visualize_graph(G):
    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G)
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=1000)
    nx.draw_networkx_labels(G, pos)
    
    # Draw edges with different colors based on type
    internal_edges = [(u, v) for u, v, d in G.edges(data=True) 
                     if d.get('type') == 'internal']
    cross_edges = [(u, v) for u, v, d in G.edges(data=True) 
                  if d.get('type') == 'cross_book']
    
    nx.draw_networkx_edges(G, pos, edgelist=internal_edges, edge_color='b')
    nx.draw_networkx_edges(G, pos, edgelist=cross_edges, edge_color='r')
    
    plt.title("Graph Visualization (Blue: Internal, Red: Cross-book)")
    plt.axis('off')
    plt.show()

def print_justifications(G):
    for u, v, d in G.edges(data=True):
        if 'justification' in d:
            print(f"\nConnection: {u} -> {v}")
            print(f"Justification: {d['justification']}")

if __name__ == "__main__":
    G = load_and_create_graph('C:/Users/49151/Documents/python/network/multi_graph_network/combined_analysis_80.json')
    analysis = analyze_graph(G)
    
    print(f"Network Analysis:")
    print(f"Nodes: {analysis['num_nodes']}")
    print(f"Edges: {analysis['num_edges']}")
    print(f"Cross-book relationships: {analysis['cross_book_count']}")
    print(f"Justified relationships: {analysis['justified_edges_count']}")
    
    visualize_graph(G)
    print_justifications(G)
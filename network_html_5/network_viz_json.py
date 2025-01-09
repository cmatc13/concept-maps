import json
import networkx as nx
from pyvis.network import Network
import community.community_louvain as community_louvain

def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def create_graph_from_json(json_data):
    # Create a new networkx graph
    G = nx.Graph()
    
    # Create a dictionary to store node descriptions
    node_descriptions = {}
    
    # Add nodes with descriptions
    for concept in json_data['concepts']:
        name = concept['name']
        description = concept.get('description', '')  # Use get() to handle missing descriptions
        # Create a clean tooltip with both name and description
        tooltip = f"{name}\n\n{description}" if description else name
        G.add_node(name, title=tooltip, description=description)
        node_descriptions[name] = description
    
    # Add edges with weights
    for relationship in json_data['relationships']:
        source = relationship['source']
        target = relationship['target']
        weight = float(relationship.get('weight', 1.0))  # Default weight to 1.0 if not specified
        
        # Only add edge if both nodes exist
        if source in node_descriptions and target in node_descriptions:
            G.add_edge(source, target, weight=weight)
        else:
            print(f"Warning: Edge between '{source}' and '{target}' skipped - one or both nodes missing")
    
    return G

def create_interactive_visualization(file_path, output_file="network.html"):
    try:
        # Read and parse the JSON file
        json_data = read_json_file(file_path)
        G = create_graph_from_json(json_data)
        
        if len(G.nodes()) == 0:
            raise ValueError("No valid nodes found in the input file")
        
        # Find communities using Louvain method
        communities = community_louvain.best_partition(G)
        
        # Create a pyvis network
        net = Network(
            height="750px",
            width="100%",
            bgcolor="#222222",
            font_color="white"
        )
        
        # Calculate node degrees for sizing
        node_degrees = dict(G.degree)
        max_degree = max(node_degrees.values()) if node_degrees else 1
        
        # Add nodes with properties
        for node in G.nodes():
            # Get node attributes, with fallbacks
            title = G.nodes[node].get('title', node)
            size = 20 + (30 * node_degrees[node] / max_degree)  # Normalized sizing
            
            net.add_node(
                node,
                label=node,
                title=title,
                size=size,
                group=communities.get(node, 0)
            )
        
        # Add edges with weights
        for edge in G.edges(data=True):
            net.add_edge(
                edge[0], 
                edge[1], 
                value=edge[2].get('weight', 1.0),  # Use weight for edge thickness
                title=f"Weight: {edge[2].get('weight', 1.0)}"  # Add weight as tooltip
            )
        
        # Configure physics and other options
        net.set_options("""
        {
            "nodes": {
                "borderWidth": 2,
                "borderWidthSelected": 4,
                "opacity": 0.9,
                "font": {
                    "size": 14,
                    "face": "Tahoma"
                }
            },
            "edges": {
                "color": {
                    "inherit": true,
                    "opacity": 0.7
                },
                "smooth": {
                    "type": "continuous",
                    "forceDirection": "none"
                },
                "width": 2
            },
            "physics": {
                "barnesHut": {
                    "gravitationalConstant": -80000,
                    "springConstant": 0.001,
                    "springLength": 200
                },
                "minVelocity": 0.75
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 200,
                "zoomView": true,
                "dragView": true
            }
        }
        """)
        
        # Save the network
        net.save_graph(output_file)
        print(f"Network visualization has been saved to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: Input file '{file_path}' not found")
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in '{file_path}'")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Input and output file paths - modify these as needed
    input_file = "C:/Users/49151/Documents/python/network/multi_graph_network/combined_analysis_90.json"
    output_file = "C:/Users/49151/Documents/python/network/network_html_5/combined_analysis_90.html"
    
    # Create the visualization
    create_interactive_visualization(input_file, output_file)
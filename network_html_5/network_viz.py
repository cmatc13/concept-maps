import networkx as nx
from pyvis.network import Network
import xml.etree.ElementTree as ET
import community.community_louvain as community_louvain

def read_graphml_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        xml_content = file.read()
    return xml_content

def parse_graphml(xml_content):
    # Parse the XML content
    root = ET.fromstring(xml_content)
    
    # Create a new networkx graph
    G = nx.Graph()
    
    # Get the graph element
    graph = root.find('.//{http://graphml.graphdrawing.org/xmlns}graph')
    
    # Parse nodes and their descriptions
    for node in graph.findall('.//{http://graphml.graphdrawing.org/xmlns}node'):
        node_id = node.get('id')
        # Look for description in data elements
        desc = node.find('.//{http://graphml.graphdrawing.org/xmlns}data[@key="d3"]')
        # If no description found, try looking for the name
        if desc is None or not desc.text:
            desc = node.find('.//{http://graphml.graphdrawing.org/xmlns}data[@key="d2"]')
        
        description = desc.text if desc is not None and desc.text else node_id
        
        # Create a clean tooltip with both ID and description
        tooltip = f"{node_id}\n\n{description}"
        G.add_node(node_id, title=tooltip)
    
    # Parse edges
    for edge in graph.findall('.//{http://graphml.graphdrawing.org/xmlns}edge'):
        source = edge.get('source')
        target = edge.get('target')
        weight_elem = edge.find('.//{http://graphml.graphdrawing.org/xmlns}data[@key="d9"]')
        weight = float(weight_elem.text) if weight_elem is not None else 1.0
        G.add_edge(source, target, weight=weight)
    
    return G

def create_interactive_visualization(file_path, output_file="network.html"):
    # Read and parse the GraphML file
    xml_content = read_graphml_file(file_path)
    G = parse_graphml(xml_content)
    
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
    max_degree = max(node_degrees.values())
    
    # Add nodes with properties
    for node in G.nodes():
        size = 20 + (30 * node_degrees[node] / max_degree)  # Normalized sizing
        net.add_node(
            node,
            label=node,
            title=G.nodes[node]['title'],
            size=size,
            group=communities[node]
        )
    
    # Add edges
    for edge in G.edges():
        net.add_edge(edge[0], edge[1])
    
    # Configure physics and other options
    net.set_options("""
    {
        "nodes": {
            "borderWidth": 2,
            "borderWidthSelected": 4,
            "opacity": 0.9
        },
        "edges": {
            "color": {
                "inherit": true,
                "opacity": 0.7
            },
            "smooth": {
                "type": "continuous",
                "forceDirection": "none"
            }
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
            "tooltipDelay": 200
        }
    }
    """)
    
    # Save the network
    net.save_graph(output_file)
    print(f"Network visualization has been saved to {output_file}")

if __name__ == "__main__":
    # Input and output file paths - modify these as needed
    input_file = "C:/Users/49151/Documents/python/network/embeddings_from_graphs_4/berkshire_letters_embedded.graphml"
    output_file = "C:/Users/49151/Documents/python/network/network_html_5/concept_network_berkshire_letters3.html"
    
    # Create the visualization
    create_interactive_visualization(input_file, output_file)
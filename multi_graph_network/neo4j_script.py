from neo4j import GraphDatabase

def run_cypher_script(instance_id, instance_name, user, password, cypher_file):
    # Construct the connection URI using the instance ID
    uri = f"neo4j+s://{instance_id}.databases.neo4j.io:7687"
    print(f"Connecting to {instance_name} at {uri}")
    
    # Connect to the Neo4j database
    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        with driver.session() as session:
            # Read the Cypher script
            with open(cypher_file, 'r') as file:
                cypher_script = file.read()

            # Split the script into individual statements if needed
            cypher_statements = cypher_script.split(';')
            
            for statement in cypher_statements:
                # Clean up whitespace and skip empty statements
                if statement.strip():
                    session.run(statement.strip())
            print("Cypher script executed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        driver.close()

NEO4J_URI="neo4j+s://106e45ee.databases.neo4j.io:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="2_ELHdJySPiY5KJzXcUD8Ijr8wB7YajC1nwbXyBpHn0"
AURA_INSTANCEID="106e45ee"
AURA_INSTANCENAME="Instance01"
CYTHER_SCRIPT_PATH = "output_with_indexes_constraints.cypher"  # Path to your Cypher file

# Run the function
run_cypher_script(AURA_INSTANCEID, AURA_INSTANCENAME, NEO4J_USER, NEO4J_PASSWORD, CYTHER_SCRIPT_PATH)


import json

def generate_cypher_script_with_indexes_and_constraints(json_file, output_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    concepts = data.get('concepts', [])
    
    cypher_lines = [
        "// Constraints to ensure unique node properties",
        "CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE;",
        "CREATE CONSTRAINT sourcebook_name IF NOT EXISTS FOR (s:SourceBook) REQUIRE s.name IS UNIQUE;",
        "",
        "// Indexes for optimizing queries",
        "CREATE INDEX concept_description IF NOT EXISTS FOR (c:Concept) ON (c.description);",
        "CREATE INDEX sourcebook_name_index IF NOT EXISTS FOR (s:SourceBook) ON (s.name);",
        ""
    ]
    
    source_books = set()
    
    # Create nodes for concepts and source books
    for concept in concepts:
        name = concept.get('name', '').replace("'", "\\'")
        description = concept.get('description', '').replace("'", "\\'")
        source_book = concept.get('source_book', '').replace("'", "\\'")
        
        cypher_lines.append(f"CREATE (:Concept {{name: '{name}', description: '{description}'}});")
        if source_book:
            source_books.add(source_book)
    
    for source_book in source_books:
        cypher_lines.append(f"CREATE (:SourceBook {{name: '{source_book}'}});")
    
    # Create edges between concepts and source books
    for concept in concepts:
        name = concept.get('name', '').replace("'", "\\'")
        source_book = concept.get('source_book', '').replace("'", "\\'")
        
        if source_book:
            cypher_lines.append(f"""
            MATCH (c:Concept {{name: '{name}'}}), (s:SourceBook {{name: '{source_book}'}})
            CREATE (c)-[:JUSTIFIED_BY]->(s);
            """)
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(cypher_lines))
    
    print(f"Cypher script with indexes and constraints saved to {output_file}")

# Usage:
# Replace 'combined_analysis.json' with your JSON file and 'output_with_indexes_constraints.cypher' with your desired output file
generate_cypher_script_with_indexes_and_constraints('combined_analysis.json', 'output_with_indexes_constraints.cypher')

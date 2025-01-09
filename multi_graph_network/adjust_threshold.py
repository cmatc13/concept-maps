import json

def filter_json(input_file, output_file, min_weight=0.9):
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    data['relationships'] = [rel for rel in data['relationships'] 
                           if rel['weight'] >= min_weight]
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=4)

# Usage
filter_json('combined_analysis.json', 'combined_analysis_90.json', 0.9)
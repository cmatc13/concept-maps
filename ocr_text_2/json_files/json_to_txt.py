import json
import re

def json_to_txt(json_file, txt_file):
    try:
        # Read the JSON file
        with open(json_file, 'r', encoding='utf-8') as infile:
            data = json.load(infile)
        
        # Initialize a list to collect cleaned text values
        cleaned_texts = []
        
        # Recursive function to extract 'text' values from nested JSON
        def extract_text(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == 'text' and isinstance(value, str):
                        # Clean the text: remove non-word characters, convert to lowercase
                        cleaned_text = re.sub(r'\W+', ' ', value).lower().strip()
                        cleaned_texts.append(cleaned_text)
                    else:
                        extract_text(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_text(item)
        
        # Start extraction
        extract_text(data)
        
        # Join all cleaned text values into one string, separated by spaces
        final_text = ' '.join(cleaned_texts)
        
        # Write the final cleaned text to the output file
        with open(txt_file, 'w', encoding='utf-8') as outfile:
            outfile.write(final_text)
        
        print(f"Text successfully extracted and written to {txt_file}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
json_to_txt('./json_files/same_as_ever.json', 'same_as_ever.txt')

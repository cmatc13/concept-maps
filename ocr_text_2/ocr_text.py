import pytesseract
from PIL import Image
import glob
import os
print(pytesseract.pytesseract.tesseract_cmd)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

print(pytesseract.pytesseract.tesseract_cmd)
def extract_text_from_images(input_path, output_file):
    # Get all PNG files in the input path in numerical order
    image_files = sorted(glob.glob(os.path.join(input_path, "*.png")), key=lambda x: int(os.path.basename(x).split('.')[0]))


    # Create or overwrite output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for image_file in image_files:
            # Open the image
            image = Image.open(image_file)
            
            # Extract text using Tesseract
            text = pytesseract.image_to_string(image)
            
            # Write filename and extracted text to file
            f.write(f"=== {os.path.basename(image_file)} ===\n")
            f.write(text)
            f.write("\n\n")

if __name__ == "__main__":
    input_path = "C:/Users/49151/Documents/python/network/kindle_screenshots_1/Berkshire Letters"  # Current directory
    output_file = "C:/Users/49151/Documents/python/network/ocr_text_2/berkshire_letters2.txt"
    extract_text_from_images(input_path, output_file)
import pyautogui
import time
from pathlib import Path
from PIL import ImageGrab
import os

def capture_kindle_pages(num_pages, save_dir):
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    
    input("Open Kindle to first page and press Enter...")
    
    with pyautogui.hold('alt'):
        pyautogui.press('tab')
    time.sleep(0.5)

    for i in range(1, num_pages):
        # Navigate page
        pyautogui.keyDown('down')
        time.sleep(0.5)
        pyautogui.keyUp('down')
        
        # Take and save screenshot
        screenshot = ImageGrab.grab()
        screenshot.save(f"{save_dir}/{i}.png")
        time.sleep(0.5)

if __name__ == "__main__":
    num_pages = int(input("Number of pages: "))
    book_name = input("Enter book name for folder: ")
    save_dir = f"./{book_name}"
    capture_kindle_pages(num_pages, save_dir)
import requests
import gzip
import json
import os
import shutil
import logging
from config import UPSTOX_MCX_URL, DATA_FILENAME

# Configure logging to console only (no separate log file)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Get logger for this module
logger = logging.getLogger(__name__)

def ensure_directories(file_path):
    """Ensure the directory for the file path exists"""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def download_and_process_instruments(download_url=UPSTOX_MCX_URL, output_filename=DATA_FILENAME):
    """
    Downloads the MCX instruments file from Upstox, decompresses it,
    and returns the loaded JSON data.
    """
    try:
        ensure_directories(output_filename)
        logger.info(f"Downloading instruments from {download_url}...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        compressed_file = "temp_mcx.json.gz"
        
        with open(compressed_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info("Download complete. Decompressing...")
        
        with gzip.open(compressed_file, 'rb') as f_in:
            with open(output_filename, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        logger.info(f"Decompression complete. Saved to {output_filename}")
        
        # Clean up compressed file
        if os.path.exists(compressed_file):
            os.remove(compressed_file)
            
        # Load and return data
        with open(output_filename, 'r') as f:
            data = json.load(f)
            logger.info(f"Loaded {len(data)} instruments.")
            return data

    except Exception as e:
        logger.error(f"Error downloading or processing instruments: {e}")
        return None

def main():
    logger.info("Starting Main Application...")
    logger.info("Fetching MCX Instruments...")
    instruments = download_and_process_instruments()
    
    if instruments:
        logger.info(f"Successfully loaded {len(instruments)} instruments.")
        # Proceed with further logic here
    else:
        logger.error("Failed to load instruments.")

if __name__ == "__main__":
    main()

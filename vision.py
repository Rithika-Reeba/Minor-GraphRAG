"""CLI helper for wardrobe image analysis. Prefer the Streamlit app for the full pipeline."""

from pathlib import Path

from src.ingestion.vision import analyze_image

if __name__ == "__main__":
    image = Path(__file__).with_name("wardrobe.png")
    if not image.exists():
        raise SystemExit("wardrobe.png not found next to vision.py")
    print(analyze_image(image))

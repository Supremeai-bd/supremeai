import os
import httpx
from typing import Dict, Any, Optional
from loguru import logger

class HFImageGenerator:
    """
    Generates images using HuggingFace Inference API.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("HF_API_KEY", "")
        self.default_model = "stabilityai/stable-diffusion-xl-base-1.0"

    def generate_image(self, prompt: str, model: Optional[str] = None, output_path: str = "data/generated_image.png") -> Dict[str, Any]:
        """
        Calls HuggingFace Inference API text-to-image pipeline.
        """
        model = model or self.default_model
        if not self.api_key:
            logger.warning("HF_API_KEY is not set. Image generation will fall back to mock mode.")
            return self._mock_generation(prompt, output_path)

        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"https://api-inference.huggingface.co/models/{model}"
        
        try:
            logger.info(f"Generating image via HF Model '{model}' with prompt: {prompt}")
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, headers=headers, json={"inputs": prompt})
                
                # Check for model loading
                if res.status_code == 503:
                    estimated_time = res.json().get("estimated_time", 20.0)
                    logger.warning(f"HF Model is loading. Estimated time: {estimated_time}s. Retrying once...")
                    import time
                    time.sleep(estimated_time)
                    res = client.post(url, headers=headers, json={"inputs": prompt})

                res.raise_for_status()
                image_data = res.content
                
                # Ensure directories exist
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(image_data)
                
                return {
                    "success": True,
                    "model": model,
                    "prompt": prompt,
                    "output_path": output_path,
                    "mock": False
                }
        except Exception as e:
            logger.error(f"HuggingFace image generation failed: {e}. Falling back to mock generation.")
            return self._mock_generation(prompt, output_path, error=str(e))

    def _mock_generation(self, prompt: str, output_path: str, error: Optional[str] = None) -> Dict[str, Any]:
        """Creates a placeholder image if API is offline or key is missing."""
        try:
            from PIL import Image, ImageDraw
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            img = Image.new("RGB", (512, 512), color=(73, 109, 137))
            d = ImageDraw.Draw(img)
            d.text((10, 10), f"Mock Generation\nPrompt: {prompt[:40]}...\nError: {error or 'None'}", fill=(255, 255, 0))
            img.save(output_path)
            return {
                "success": True,
                "model": "mock-generator",
                "prompt": prompt,
                "output_path": output_path,
                "mock": True
            }
        except Exception as ex:
            return {
                "success": False,
                "error": f"Mock generation failed: {ex}"
            }

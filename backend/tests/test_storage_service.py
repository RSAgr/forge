from io import BytesIO

import pytest
from PIL import Image

from app.services.storage_service import validate_image


def png_image():
    data = BytesIO()
    Image.new("RGB", (4, 4), "blue").save(data, format="PNG")
    return data.getvalue()


def test_valid_image_is_accepted():
    validate_image(png_image(), "image/png")


def test_content_type_must_match_image_bytes():
    with pytest.raises(ValueError, match="does not match"):
        validate_image(png_image(), "image/jpeg")


def test_non_image_data_is_rejected():
    with pytest.raises(ValueError, match="not a valid"):
        validate_image(b"not an image", "image/png")

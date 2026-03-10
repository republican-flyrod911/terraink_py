from __future__ import annotations

from PIL import Image

from terraink_py.render import apply_png_fades


def test_apply_png_fades_adds_edge_alpha_gradients() -> None:
    image = Image.new("RGBA", (2, 20), (0, 0, 0, 0))

    apply_png_fades(image, "#123456")

    alpha_values = [
        image.getpixel((0, y))[3] for y in range(image.height)  # type: ignore[index]
    ]

    assert alpha_values[0] == 255
    assert alpha_values[4] == 0
    assert alpha_values[10] == 0
    assert alpha_values[15] == 0
    assert alpha_values[-1] == 255

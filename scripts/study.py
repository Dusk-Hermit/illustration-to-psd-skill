"""Create and verify a PhotoCraft PSD for an illustration color study."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
from PIL import Image, ImageOps
from psd_tools import PSDImage

from separate import STAGES, separate


REFERENCE = "00 原图参考（默认隐藏）"
NAMES = [REFERENCE, *(f"{i:02} {name}" for i, name in reversed(list(enumerate(STAGES, 1))))]


def png_bytes(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def write_ora(path, size, layers, composite):
    root = ET.Element("image", w=str(size[0]), h=str(size[1]), version="0.0.3", name="Color Study")
    stack = ET.SubElement(root, "stack")
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "image/openraster")
        for index, (name, image) in enumerate(zip(NAMES, layers)):
            entry = f"data/layer{index}.png"
            archive.writestr(entry, png_bytes(image))
            ET.SubElement(stack, "layer", name=name, src=entry, x="0", y="0", opacity="1.0",
                          visibility="hidden" if index == 0 else "visible",
                          attrib={"composite-op": "svg:src-over"})
        archive.writestr("stack.xml", ET.tostring(root, encoding="utf-8"))
        archive.writestr("mergedimage.png", png_bytes(composite.convert("RGB")))


def canonical_pixels(image):
    pixels = np.array(image.convert("RGBA"))
    pixels[pixels[..., 3] == 0] = 0
    return pixels


def digest(pixels):
    return hashlib.sha256(pixels.tobytes()).hexdigest()


def layer_image(layer, size):
    rendered = Image.new("RGBA", size)
    pixels = layer.topil()
    if pixels is not None:
        rendered.paste(pixels.convert("RGBA"), (layer.left, layer.top))
    return rendered


def inspect_psd(path, expected_layers=None, expected_composite=None):
    psd = PSDImage.open(path)
    if expected_composite is not None and psd.size != expected_composite.size:
        raise ValueError("PSD canvas dimensions did not match.")
    layers = list(reversed(psd))
    if [(layer.name, layer.visible) for layer in layers] != [
        (name, index != 0) for index, name in enumerate(NAMES)
    ]:
        raise ValueError("PSD layer names, stack order, or visibility did not match.")
    stats = []
    recomposed = Image.new("RGBA", psd.size)
    for index, layer in enumerate(layers):
        rendered = layer_image(layer, psd.size)
        actual = canonical_pixels(rendered)
        if expected_layers is not None and not np.array_equal(actual, canonical_pixels(expected_layers[index])):
            raise ValueError(f"PSD pixels differ in layer {layer.name}.")
        stats.append({"name": layer.name, "visible": layer.visible,
                      "nontransparent_pixels": int(np.count_nonzero(actual[..., 3])),
                      "sha256_rgba": digest(actual)})
        if layer.visible:
            recomposed = Image.alpha_composite(rendered, recomposed)
    cached = np.asarray(psd.topil().convert("RGB"))
    expected = np.asarray((expected_composite or recomposed).convert("RGB"), dtype=np.int16)
    difference = int(np.abs(cached - expected).max())
    if difference > 2:
        raise ValueError(f"PSD composite differs by up to {difference} RGB levels.")
    return {"size": list(psd.size), "layers_top_first": stats,
            "sha256_composite_rgb": digest(cached), "max_composite_rgb_delta": difference}


def preview(path, output):
    psd = PSDImage.open(path)
    layers = {layer.name: layer for layer in psd}
    reference = layer_image(layers[REFERENCE], psd.size)
    base = Image.alpha_composite(layer_image(layers[NAMES[-1]], psd.size),
                                 layer_image(layers[NAMES[-2]], psd.size))
    panels = []
    for image in (reference, base, psd.topil()):
        panel = Image.new("RGBA", psd.size, "white")
        panel.alpha_composite(image.convert("RGBA"))
        panel.thumbnail((600, 900))
        panels.append(panel.convert("RGB"))
    width, height = panels[0].size
    sheet = Image.new("RGB", (3 * width + 16, height), "#d0d0d0")
    for index, panel in enumerate(panels):
        sheet.paste(panel, (index * (width + 8), 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def create(args):
    cli = args.photocraft or os.environ.get("PHOTOCRAFT_CLI") or shutil.which("photocraft-cli")
    if not cli:
        raise ValueError("Set --photocraft or PHOTOCRAFT_CLI, or put photocraft-cli on PATH.")
    output = args.output.resolve()
    if output.suffix.lower() != ".psd" or output in {args.source.resolve(), args.recipe.resolve()}:
        raise ValueError("Choose a separate output path ending in .psd.")
    recipe = json.loads(args.recipe.read_text(encoding="utf-8-sig"))
    with Image.open(args.source) as source:
        oriented = ImageOps.exif_transpose(source).convert("RGBA")
        reference = Image.frombytes("RGBA", oriented.size, oriented.tobytes())
    stages = separate(reference, recipe)
    composite = Image.new("RGBA", reference.size)
    for stage in stages:
        composite = Image.alpha_composite(composite, stage)
    layers = [reference, *reversed(stages)]
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".study-", dir=output.parent) as folder:
        ora = Path(folder) / "study.ora"
        temporary = ora.with_suffix(".psd")
        write_ora(ora, reference.size, layers, composite)
        converted = subprocess.run([str(cli), "convert", "--no-gpu", str(ora), str(temporary)],
                                   capture_output=True, text=True, encoding="utf-8", errors="replace")
        if converted.returncode:
            raise ValueError(converted.stderr.strip() or converted.stdout.strip() or "PhotoCraft conversion failed.")
        stats = inspect_psd(temporary, layers, composite)
        temporary.replace(output)
    return stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    export = subcommands.add_parser("create", help="Build and validate a layered study PSD.")
    for flag in ("source", "recipe", "output"):
        export.add_argument(f"--{flag}", type=Path, required=True)
    export.add_argument("--photocraft", help="PhotoCraft CLI executable path.")
    inspect = subcommands.add_parser("inspect", help="Verify a PSD and print decoded pixel fingerprints.")
    inspect.add_argument("psd", type=Path)
    compare = subcommands.add_parser("preview", help="Save a side-by-side reference, bases, and composite PNG.")
    compare.add_argument("psd", type=Path)
    compare.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "preview":
            if args.output.suffix.lower() != ".png":
                raise ValueError("Choose a preview path ending in .png.")
            preview(args.psd, args.output)
            return
        stats = create(args) if args.command == "create" else inspect_psd(args.psd)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(stats, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

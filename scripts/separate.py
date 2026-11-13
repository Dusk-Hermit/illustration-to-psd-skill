"""Build paintable raster stages from source colors and coarse material outlines."""

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from skimage.color import rgb2lab


STAGES = (
    "背景与环境大底", "人物与道具固有色", "环境暗部与投影", "人物与道具暗面",
    "亮面与反光", "中间色与材质转折", "脸手与配饰细节", "细线、碎光与短点",
)
ENVIRONMENT = {"background", "environment"}
ROLES = ENVIRONMENT | {"subject", "skin", "accessory", "dark"}


def material_map(recipe, size):
    width, height = size
    materials = recipe["materials"]
    if not 1 <= len(materials) <= 255 or materials[0]["role"] != "background":
        raise ValueError("Use 1–255 materials, with a background at index 0.")
    if any(m["role"] not in ROLES or type(m["k"]) is not int or not 1 <= m["k"] <= 32
           for m in materials):
        raise ValueError("Each material needs a supported role and an integer k from 1 to 32.")
    labels = np.zeros((height, width), np.uint8)
    for shape in recipe["shapes"]:
        index = shape["material"]
        points = np.asarray(shape["points"], dtype=float)
        if (type(index) is not int or not 0 <= index < len(materials)
                or points.ndim != 2 or points.shape[1] != 2 or len(points) < 3
                or not np.isfinite(points).all() or np.any((points < 0) | (points > 1000))):
            raise ValueError("A polygon needs a valid material index and 3+ points in 0–1000.")
        pixels = np.rint(points * np.array([width, height]) / 1000).astype(np.int32)
        cv2.fillPoly(labels, [np.minimum(pixels, [width - 1, height - 1]).astype(np.int32)], index)
    for index, material in enumerate(materials):
        if not np.any(labels == index):
            raise ValueError(f"Material {index} ({material['name']}) has no visible pixels.")
    return labels


def color_clusters(rgb, semantic, materials):
    smoothed = cv2.bilateralFilter(rgb, 7, 21, 3)
    lab = rgb2lab(smoothed / 255).astype(np.float32)
    labels = np.zeros(semantic.shape, np.int32)
    base_colors = []
    offset = 0
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 45, 0.07)
    for index, material in enumerate(materials):
        mask = semantic == index
        values = lab[mask]
        sample = values[::max(1, len(values) // 18000)].copy()
        k = min(material["k"], len(sample))
        _, _, centers = cv2.kmeans(sample, k, None, criteria, 2, cv2.KMEANS_PP_CENTERS)
        assigned = [((chunk[:, None] - centers) ** 2).sum(2).argmin(1)
                    for chunk in np.array_split(values, (len(values) + 19999) // 20000)]
        labels[mask] = np.concatenate(assigned) + offset
        base_colors.append(np.percentile(rgb[mask], 55, axis=0).round().astype(np.uint8))
        offset += k
    return labels, np.asarray(base_colors), offset


def connected_patches(labels, semantic, roles, count):
    patches = np.full(labels.shape, -1, np.int32)
    owners = []
    for color in range(count):
        components, _ = ndi.label(labels == color)
        for component, box in enumerate(ndi.find_objects(components), 1):
            if box is None:
                continue
            region = components[box] == component
            role_id = int(semantic[box][region][0])
            minimum = 9 if roles[role_id] in {"skin", "accessory", "dark"} else 18
            if region.sum() >= minimum:
                patches[box][region] = len(owners)
                owners.append(role_id)
    for index in range(len(roles)):
        material = semantic == index
        missing = material & (patches < 0)
        seeds = material & (patches >= 0)
        if missing.any() and seeds.any():
            nearest = ndi.distance_transform_edt(~seeds, return_distances=False, return_indices=True)
            patches[missing] = patches[tuple(nearest[:, missing])]
    return patches, owners


def patch_stage(role, area, width, lightness, delta):
    if role == "skin" or (role == "accessory" and area < 1300):
        return 6
    if (area < 65 or (width < 2.5 and area < 800)) and (lightness < 55 or lightness > 84):
        return 7
    if delta > 12:
        return 4
    if delta < -10:
        return 2 if role in ENVIRONMENT else 3
    return 5


def paint_patch(region, rgb, lab, role, base_lightness):
    contours, _ = cv2.findContours(region.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    loops = []
    for contour in contours:
        tolerance = 0.65
        loop = cv2.approxPolyDP(contour, tolerance, True)
        while len(loop) > 72:
            tolerance *= 1.25
            loop = cv2.approxPolyDP(contour, tolerance, True)
        if len(loop) >= 3:
            loops.append(loop)
    if not loops:
        return None

    alpha = np.zeros(region.shape, np.uint8)
    cv2.fillPoly(alpha, loops, 255)
    pixels = rgb[region]
    area = len(pixels)
    width = float(2 * ndi.distance_transform_edt(np.pad(region, 1))[1:-1, 1:-1][region].mean())
    lightness = float(np.median(lab[region]))
    stage = patch_stage(role, area, width, lightness, lightness - base_lightness)
    color = np.empty_like(rgb)
    color[:] = np.median(pixels, axis=0).round().astype(np.uint8)
    if area > 800 and width > 5:
        height, span = region.shape
        yy, xx = np.indices(region.shape)
        x, y = xx / max(span - 1, 1), yy / max(height - 1, 1)
        samples = np.column_stack([np.ones(area), x[region], y[region]])
        coefficients = np.linalg.lstsq(samples, pixels, rcond=None)[0]
        error = np.sqrt(np.mean((samples @ coefficients - pixels) ** 2))
        swing = max(np.linalg.norm(coefficients[1]), np.linalg.norm(coefficients[2]))
        if error < 10 and 7 < swing < 55:
            origin, dx, dy = coefficients.round(3)
            color = np.clip(origin + x[..., None] * dx + y[..., None] * dy, 0, 255).astype(np.uint8)
    return stage, area, np.dstack((color, alpha))


def separate(reference, recipe):
    cv2.setNumThreads(2)
    cv2.setRNGSeed(19)
    rgb = np.array(Image.alpha_composite(Image.new("RGBA", reference.size, "white"), reference).convert("RGB"))
    materials = recipe["materials"]
    roles = [material["role"] for material in materials]
    semantic = material_map(recipe, reference.size)
    labels, base_colors, count = color_clusters(rgb, semantic, materials)
    patches, owners = connected_patches(labels, semantic, roles, count)
    lab = rgb2lab(rgb / 255)[..., 0]
    base_lab = rgb2lab(base_colors[None] / 255)[0, :, 0]
    subject = np.isin(semantic, [index for index, role in enumerate(roles) if role not in ENVIRONMENT])
    base = base_colors[semantic]
    # Background underpainting continues below the visible subject.
    background = np.where(subject[..., None], base_colors[0], base)
    layers = [
        Image.fromarray(np.dstack((background, np.full(semantic.shape, 255, np.uint8)))),
        Image.fromarray(np.dstack((base, subject.astype(np.uint8) * 255))),
        *(Image.new("RGBA", reference.size) for _ in STAGES[2:]),
    ]
    tiles = []
    for index, box in enumerate(ndi.find_objects(patches + 1)):
        if box is None:
            continue
        owner = owners[index]
        result = paint_patch(patches[box] == index, rgb[box], lab[box], roles[owner], base_lab[owner])
        if result is not None:
            stage, area, tile = result
            # Protect neighboring materials when simplified contours cross their borders.
            tile[..., 3][semantic[box] != owner] = 0
            tiles.append((area, stage, tile, (box[1].start, box[0].start)))
    for _, stage, tile, origin in sorted(tiles, key=lambda patch: -patch[0]):
        layers[stage].alpha_composite(Image.fromarray(tile), origin)
    return layers

# Material recipe and brush guidance

```json
{
  "materials": [
    {"name": "Paper", "role": "background", "k": 4},
    {"name": "Jacket", "role": "subject", "k": 10},
    {"name": "Face", "role": "skin", "k": 8}
  ],
  "shapes": [
    {"material": 1, "points": [[210, 460], [730, 440], [850, 1000], [150, 1000]]},
    {"material": 2, "points": [[310, 180], [610, 190], [620, 390], [470, 470], [310, 380]]}
  ]
}
```

Use the displayed image after EXIF orientation. Coordinates run from 0 to 1000 on each axis, with the origin at the upper left. Divide pixel x by image width and pixel y by image height, then multiply by 1000. Uncovered pixels belong to material 0. Later polygons take precedence at overlaps. Trace back-to-front, then inspect the base layers for missed overlaps or missing pieces. Set material names to recognizable labels.

Use `background` for the canvas default, `environment` for scenery, `subject` for hair/clothes/props, `skin` for exposed skin, `accessory` for small accents, and `dark` for small dark objects that need finer regions. Each material needs visible pixels. `k` is the number of Lab color clusters. Start around 3–6 for nearly flat material and 8–14 for material with several visible colors. Lower it if similar shades fragment into many unnecessary shapes.

Split objects with different base colors even if they share a role. For example, use separate entries for two faces or two differently colored controllers because each entry receives one base color. For glass and other transparent objects, trace the visible shapes through the glass where they affect the composition. Treat the rim or reflections separately. One opaque base over the whole surface will hide those shapes in the base-stage preview.

| Stage | Repainting technique |
| --- | --- |
| Background and environment bases | Large opaque round brush or lasso fill |
| Subject and prop bases | Opaque hard round or lasso fill, following occlusion |
| Environment shadows | Lay in closed silhouettes with a hard brush, then soften local transitions |
| Subject shadows | Hard round or lasso for shadow masses, tapered small round for narrow folds |
| Light and reflected light | Hard edge for the silhouette, low-opacity soft round within the shape |
| Midtones and material transitions | Hard round for color planes, soft round for broad transitions |
| Skin and accessory details | Small hard round for facial planes and small accents |
| Thin marks and highlights | Tapered round for lines, small hard round for dots and short marks |

Within each material the script uses bilateral smoothing and Lab clustering, merges tiny components into nearby patches of the same material, simplifies contours, and fills with a representative color or a simple planar RGB ramp. The darkest and lightest shapes are assigned relative to the material's base color. Empty stages are valid, especially for flat or monochrome illustrations. On a resolution very different from 1000 pixels tall, fixed pixel thresholds can retain a different level of detail.

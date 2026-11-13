---
name: illustration-to-psd-skill
description: Use when the user wants to 拆色 an illustration, turn a flattened image into an editable layered PSD, or study how to repaint it in stages with ordinary brushes.
---

# Illustration to layered PSD

1. Inspect the actual source image, respecting EXIF orientation. Plan coarse outlines for visually distinct materials such as skin, hair, clothing, props, and background. A material can have several disconnected polygons. Keep small highlights and texture inside the parent material unless they need separate treatment.
2. Save an image-specific JSON recipe beside the output. Use [recipe format and brush guidance](recipe.md). Draw the outlines over a reference with a coordinate grid if positions are hard to estimate. Use the same uncropped image orientation for the recipe and export.
3. Install the Python dependencies from `requirements.txt` if needed. Find the PhotoCraft CLI via `PHOTOCRAFT_CLI`, PATH, or an available local executable. Run the bundled script using paths relative to this skill's directory:

   ```text
   python scripts/study.py create --source IMAGE --recipe RECIPE.json --output STUDY.psd --photocraft PHOTOCRAFT_CLI_PATH
   ```

   Quote paths containing spaces or shell metacharacters. Omit `--photocraft` if the executable is already configured. If PhotoCraft is unavailable, report the missing dependency.
4. Run `python scripts/study.py preview STUDY.psd REVIEW.png` to compare the reference, the first two stages, and the final composite side by side. If a mask cuts across a visible feature or creates an obvious color spill, adjust the recipe and rerun. Keep eight named stages even when a stage is empty. The PSD includes a hidden source reference and only the stage layers appear in the default composite.
5. For a repeatability check, run `create` again with the same source, recipe, and environment into a second PSD. Compare the `inspect` JSON for both files. Matching decoded layer and composite fingerprints establish repeatability for that recipe. A separately authored recipe can produce different results.

Describe the PSD as a repainting study derived from the visible pixels. Flat source images do not reveal the original layers, covered content, or the artist's actual sequence. Deliver the PSD and any other artifacts the user asked for.

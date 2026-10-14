# 3D model sources

The site's 3D models are made in Blender. This folder keeps each model's `.blend` source and its
raw glTF export; the compressed models the site loads live in `frontend/public/3d/`, with a poster
image for each in `frontend/public/3d/posters/`. Running the site never needs Blender.

| Source               | Export             | What it is                                                                                                                   |
| -------------------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| `cricket-ball.blend` | `cricket-ball.glb` | The ball: leather, a raised seam and four rows of stitching (about 11,800 triangles).                                        |
| `stumps.blend`       | `stumps.glb`       | Three stumps and two bails to the Laws' sizes, each its own node so it can move.                                             |
| `bowled.blend`       | `bowled.glb`       | Both, composed as "bowled", with its camera. Its scene `Hero` holds the camera and turn of the ball poster on the home page. |
| `stadium.blend`      | `stadium.glb`      | A generic floodlit oval stadium (not a real ground) with its camera, built by `stadium.py`; posters for night and day.       |

One unit is 36 mm, the ball's radius, except in the stadium, which is in metres. The stadium is
made by a script: `blender --python stadium.py` builds it, and in Blender's Python console
`export()` writes `stadium.glb` and `posters()` renders `stadium-night.webp` and `stadium-day.webp`
(the site shows the one for the theme).

## Tools

- Blender 5.1 or newer (built with 5.2.2 LTS).
- The Blender Lab MCP add-on (`mcp`, from the extensions repository `https://lab.blender.org/`),
  enabled, with _Allow Online Access_ on in Blender's system preferences. Its server starts with
  Blender and listens on `localhost:9876`.
- `gltf-transform` (a dev dependency of the web app).

## From Blender to the site

1. Model in Blender and save the source here as `<name>.blend`.
2. Export it here as binary glTF, `<name>.glb` (selected objects, no Draco; include the camera
   when the scene's framing matters, as `bowled.glb` does).
3. Render its poster with Cycles on a transparent background to
   `../../public/3d/posters/<name>.webp`, from the camera the site uses, so the 3D version takes
   over without a jump. The site shows the poster while the scene loads, and instead of it when
   motion is reduced, data is saved, WebGL is unavailable or the scene fails.
4. Compress every model into the web app, which also checks the budget and the posters:

   ```bash
   cd frontend
   pnpm models
   ```

   Meshopt compression with quantised attributes, no simplification (it would eat the stitching)
   and no joining (the stumps and bails stay separate). Each compressed model must stay at or
   under 400 KB.

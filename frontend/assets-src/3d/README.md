# 3D model sources

The site's 3D models are made in Blender. This folder keeps each model's `.blend` source; the
compressed models the site loads live in `frontend/public/models/`, with a poster image for each in
`frontend/public/models/posters/`. Running the site never needs Blender.

## Tools

- Blender 5.1 or newer (built with 5.2.2 LTS).
- The Blender Lab MCP add-on (`mcp`, from the extensions repository `https://lab.blender.org/`),
  enabled, with _Allow Online Access_ on in Blender's system preferences. Its server starts with
  Blender and listens on `localhost:9876`.
- `gltf-transform` (a dev dependency of the web app: `pnpm exec gltf-transform`).

## From Blender to the site

1. Model in Blender and save the source here as `<name>.blend`.
2. Export the model as binary glTF (`File > Export > glTF 2.0`, format `.glb`, selected objects).
3. Compress it into the web app:

   ```bash
   cd frontend
   pnpm exec gltf-transform optimize <exported>.glb public/models/<name>.glb --compress meshopt --texture-compress webp
   ```

4. Render a poster of the model to `public/models/posters/<name>.webp`; the site shows it while
   the 3D scene loads, and instead of it when motion is reduced or WebGL is unavailable.

Each compressed model must stay at or under 400 KB.

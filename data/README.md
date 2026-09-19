# Melovia Data Directory

This directory stores catalog data, feature artifacts, and vector bundles.

## Vector Bundles (`data/bundles/<version>/`)

All vector embeddings and associated catalog metadata are structured as immutable, versioned, checksummed bundles:
- `manifest.json`: Bundle version, creation timestamp, checksums, embedding dimensionality, and metadata schema.
- `embeddings.npy` / `embeddings.parquet`: Normalized high-dimensional audio/taste vectors.
- `tracks.parquet`: Track metadata and controlled vocabulary descriptors.
- `viz_coords.parquet`: 3D coordinates for interactive visualization only (never used in recommendation logic).

Note: All contents of `data/` (except this `README.md`) are gitignored to prevent large binary files and secrets from entering version control.

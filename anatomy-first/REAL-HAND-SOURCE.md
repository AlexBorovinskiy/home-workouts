# Research hand geometry — source and limitations

The **GLB in this directory is not a procedural hand**. Its surfaces are rearranged into separate, neutral-name scene nodes using the triangle positions of the upstream segmented STL. This file is *not yet an anatomical joint rig*.

- Scientific source: Hegdé J., Tustison N.J., Parker W.T., Yanasak N., Stumpo L.A. *An Anatomical Template for the Normalization of Medical Images of Adult Human Hands*, Diagnostics 2023, 13(12):2010. https://doi.org/10.3390/diagnostics13122010
- Original project and archive: https://github.com/HegdeUSA/Hand_template — `3D_model_of_segmented_bones.zip`
- Unmodified ZIP SHA-256: `9e2022f7fea4e7473dc22d01eefe1510bca73e316d44f45e6732ca33336558f6`
- Original binary STL: `387,692` triangular facets. Extracted by exact shared vertex bit patterns; no hand bone silhouettes invented.
- Inventory: `480` connected polygon components, `34` with at least `100` triangles. Of these, **28 components are large** (≥3,292 triangles); the rest may be small artifacts or anatomical details and need manual verification.
- GLB generated as a display-only collection of **34 unlabeled connected components**. No named bone (scaphoid, trapezium, phalanx, etc.) has been assigned on an unverified basis.
- GLB SHA-256: `00b1aa268a656172ba2e9648e5465955f3862bc4221b79eaa9607753bd5e2e38`
- The mesh is rescaled from original coordinates by 0.001 to scene metres and recentered. Relative anatomical geometry is unchanged.
- Source GitHub repository includes an **MIT LICENSE** attributed to Jay Hegdé. A NIH 3D-hosted listing appears to carry GPLv3. The exact licensing scope for this repository's data should be clarified before wider reuse or relicensing. This prototype includes the repository's license text and upstream citation.

**Not validated:** segmentation-to-bone labels, whether the extra major segment is a sesamoid/other structure, right versus left orientation, CMC joint axes, realistic hand opposition, skinning, or any exercise technique.

No changes to `anatomy-rigged/lesson.html`, existing `unified-rig-preview.html`, or the workout journal.

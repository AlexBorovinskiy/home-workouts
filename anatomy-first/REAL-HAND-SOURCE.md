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

## Preliminary identification (geometry audit, 2026-11-22)

The original MRI archive has **no original individual bone labels**. We used longitudinal orientation (+Z toward fingertips) and lateral alignment (+X toward thumb) together with measured surface proximity.

- **19 relatively confident assignments:** all 14 phalanges (thumb × 2; other four digits × 3) and all five metacarpals. Exact IDs and Russian labels live in `assets/hand-segment-labels.json`.
- **7 provisionally identified wrist segments:** capitate (13), scaphoid (14), hamate (15), trapezium (18), lunate (21), triquetrum (22), trapezoid (23). These names are *not clinically verified*, particularly the carpal surface morphology.
- **2 likely distal forearm segments:** radius (03), ulna (10); again, these are provisional labels.
- **Pisiform:** not identified as a separately connected substantial segment. The source image may omit it, fuse it with the triquetrum, or represent it differently. Do not invent it.
- **6 small auxiliary segments (29–34):** mostly near finger surfaces, may reflect segmentation irregularities. Hidden by default in the annotated viewer, not deleted.
- **14 candidate finger joint neighborhoods** with minimum surface gaps 1.10–2.15 mm are recorded in `assets/joint-surface-candidates.json`. Those nearest-surface points are **not true anatomical rotation axes** and must not be used directly for animation.

Reference for carpal row, metacarpal articulations and the position of the pisiform: OpenStax Anatomy & Physiology 2e, *Bones of the Upper Limb*, https://openstax.org/books/anatomy-and-physiology-2e/pages/8-2-bones-of-the-upper-limb ; and University of Utah Digital Dissector, https://anatomy.med.utah.edu/diganat/anatomy_tutorials/digital_dissector/index.php?add=%2Fwrist_hand&lab=29&menu=29+WristHand .

**Next acceptance gate:** resolve pisiform and validate all seven carpal mesh identities against an anatomical 3D atlas and MRI source. Do not begin CMC rigging until trapezium and first metacarpal alignment have been independently confirmed.

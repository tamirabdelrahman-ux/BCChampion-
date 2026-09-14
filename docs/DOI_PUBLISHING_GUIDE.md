# Publish BCChampion and obtain a DOI

1. Retain the written institutional/TTO response confirming that no ownership claim is required for this release.
2. Create a public GitHub repository named `BCChampion`.
3. Upload the contents of this folder to the repository.
4. Edit `CITATION.cff`: replace `YOUR-GITHUB-USERNAME` with the repository owner's GitHub username and confirm the author list.
5. Commit and push the files.
6. In GitHub, open **Actions** → **Build Windows desktop release** → **Run workflow**. Download the generated Windows ZIP and test `BCChampion.exe` on a Windows computer that does not have Python installed.
7. After validation, create a GitHub Release with tag `v1.0.0`. Attach the tested `BCChampion-Windows-v1.0.0.zip` to the release.
8. Sign in to Zenodo and connect your GitHub account.
9. In Zenodo's GitHub integration, enable the `BCChampion` repository before making the final GitHub release. If v1.0.0 was already released before enabling Zenodo, create a new patch release after activation.
10. Zenodo will archive the enabled GitHub release and assign a version-specific DOI. Record both the version DOI and the concept DOI shown by Zenodo.
11. Update the manuscript with the version DOI corresponding to BCChampion v1.0.0. Prefer the version DOI when citing the exact software used for the publication.
12. Update `CITATION.cff` and the manuscript's Code and Software Availability statement with the final DOI, then tag a documentation-only patch release if needed.

## Suggested manuscript statement

**Code and software availability:** BCChampion (version 1.0.0), the electronic blood-culture quality-monitoring application developed for this quality-improvement programme, is publicly available at [GitHub repository] and permanently archived at Zenodo (DOI: [version DOI]). The release includes source code, Windows desktop executables, documentation and synthetic demonstration data. The public release contains no patient-identifiable information, institutional credentials or hospital-specific confidential data.

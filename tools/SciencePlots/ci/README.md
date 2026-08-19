# CI matrix testing Python x Matplotlib

To update Python versions tested against (e.g., if CI becomes outdated when a new Python version becomes the latest stable), add or remove `Python3.xx_matplotlib_versions.txt` files.
See https://devguide.python.org/versions/#versions.

To update Matplotlib versions tested against (uses latest patch version `~=` of those specified in the files), check which Python versions contain binaries.
See https://pypi.org/project/matplotlib/#history > files subsection for the version of interest.

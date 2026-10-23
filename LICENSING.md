# Licensing and attribution

## License of this modified distribution

Copyright (c) 2026 Jaron-admin, for the original modifications authored by Jaron-admin.

This modified distribution of MotionPhoto2, as a whole, and Jaron-admin's original modifications are distributed under the GNU General Public License, version 3 only (SPDX: `GPL-3.0-only`). You may redistribute and modify the covered work under those terms. It is provided without warranty; see the full license in [LICENSE](LICENSE).

The root license is an unchanged copy of [SPDX's GPL-3.0-only text](https://github.com/spdx/license-list-data/blob/31ba1a50e5397e00a304dbadc76531740e89ee48/text/GPL-3.0-only.txt). The example notice in the license's application appendix does not change this project's explicit choice of version 3 only.

## Upstream code and retained MIT notice

This fork derives from [PetrVys/MotionPhoto2](https://github.com/PetrVys/MotionPhoto2), whose original copyright notice is:

> Copyright (c) 2024 Petr Vyskocil

The complete original MIT license is preserved verbatim in [LICENSES/MIT.txt](LICENSES/MIT.txt). Keep this copyright and permission notice with copies or substantial portions of the upstream software.

The upstream conversion core and unchanged legacy PowerShell code retain their original MIT terms. The upstream project has not been relicensed by this fork. Existing copyright notices, credits, and separately applicable permissions remain in effect; this change does not revoke licenses already granted for previous versions.

The fork adds a macOS Chinese interface and packaging, followed by an application icon and signing adjustments. These modifications are recorded in commits [61509f1](https://github.com/Jaron-admin/MotionPhoto2/commit/61509f1fbe3d648252e2fc7fb0c237bb891f82aa) and [39fcb1f](https://github.com/Jaron-admin/MotionPhoto2/commit/39fcb1f012c43eb981722dd83dcdf24c7f09ce8f), following upstream commit [ff46699](https://github.com/PetrVys/MotionPhoto2/commit/ff46699215f1071ada579140d73994a4be29a399). The GPL-3.0-only distribution policy applies from the licensing change dated 2026-10-23.

## Third-party components

Dependencies, bundled tools, and other separately licensed components retain their own copyrights and license terms. This policy does not replace their notices or claim ownership of their code.

The source dependency list is [requirements.txt](requirements.txt) (lxml, PyExifTool, Gooey, and six). Build configurations also use PyInstaller and, for the macOS Chinese application, Pillow and a bundled ExifTool distribution. The exact components and applicable license notices must be checked for the versions actually included in a binary; this list is not a complete binary dependency inventory. Preserve all required third-party copyright, license, and NOTICE files, including those supplied with ExifTool.

## Distributing binaries

When distributing a GPL-covered binary, provide the corresponding source for that exact build in accordance with the GPL, including relevant build scripts and modifications. Identify the source commit or release; a link only to a changing default branch does not identify the corresponding source.

Include this file, the root [LICENSE](LICENSE), [LICENSES/MIT.txt](LICENSES/MIT.txt), and the required notices for the third-party components actually distributed. Verify the contents of the final archive or application bundle before publication; the current packaging scripts do not automatically collect all of these notices.

This licensing change does not rebuild or replace existing release artifacts, and does not assert that previous binaries have been repackaged or audited under the new distribution policy.

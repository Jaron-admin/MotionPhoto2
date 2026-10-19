# Third-party code

`reverse/iso_bmff.py` and `reverse/metadata.py` derive from [yangzhen-23/video-to-live-photo](https://github.com/yangzhen-23/video-to-live-photo/tree/83b55e6e66b6cbb39e7d7acddbbb52eef1585adc), Copyright 2026 杨振, licensed under Apache License 2.0. The license is in `LICENSES/Apache-2.0.txt`. Metadata construction is extracted from `livephoto/core/apple.py`; MotionPhoto2 adds independent validation, timeline selection and streaming remux. Upstream image reencoding is not used.

Other MotionPhoto2 code retains its existing MIT license and notices. Test-only native control generation used nicing/make-live-photo as a temporary reference; that external generator is not distributed here.

The upstream NOTICE is reproduced verbatim in `LICENSES/video-to-live-photo-NOTICE.txt`, and the complete `LICENSES` directory is included in the App bundle.


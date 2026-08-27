# Stage 7C-1D ELMC Canonical Rebuild

The four exact black-and-white image-backed PDFs are the sole canonical ELMC sources. OCR-derived text PDFs are secondary indexes only. Canonical pages are rendered locally at 300 DPI, while offline Windows Traditional Chinese OCR produces transcription candidates and layout coordinates. Canonical fingerprints are derived from question image crops, not legacy text.

Question boundaries that cannot be supported by canonical page layout and detected numbering fail closed into boundary review. Visual-backed questions remain eligible when their canonical crop preserves the necessary diagram or table. OCR candidates are never Human Ground Truth, and all source pages, crops, OCR text, solutions, and audit queues remain under `.local`.

Legacy OCR records and mappings are retained as `LEGACY_OCR_UNTRUSTED`; none are reused as canonical mappings or Human Ground Truth. Production and Supabase access remain zero.

# Curriculum Master v2.7 data archive

Runtime expects this exact file when `CURRICULUM_MASTER_V27_ENABLED` is turned on:

`data/MathAI_Master_Curriculum_Skill_v2.7_G1-G12_RUNTIME_READY.zip`

The feature flag defaults OFF. Do not enable it in production until the validated v2.7 archive from the integration bundle is copied into this path and the runtime smoke tests pass.

The runtime also supports base64 chunk files matching `data/MathAI_Master_Curriculum_Skill_v2.7.zip.b64.*` for environments that cannot ship a binary archive directly.

#!/bin/bash
set -e  # detiene el pipeline si cualquier comando falla

echo "============================================"
echo "  PIPELINE T22 / T36"
echo "============================================"

# ── 1. Fix headers hamatum ────────────────────────────────────
echo ">>> [1/2] Iniciando fix_headers hamatum"
bash fix_headers_hamatum.sh
echo ">>> fix_headers completado"

# ── 2. Anotación T22 y T36 ───────────────────────────────────
echo ">>> [2/2] Iniciando anotación T22/T36"
python fun_annotate_T22_T36.py
echo ">>> Anotación T22/T36 completada"

echo "============================================"
echo "  PIPELINE COMPLETO"
echo "============================================"

# nohup python fun_predict_annotate_T16.py > predict_annotate_T16.log 2>&1 &
# tail -f predict_annotate_T16.log

# correr con 
# "nohup bash pipeline_T22_T36.sh > pipeline_T22_T36.log 2>&1 &"

# luego:
# "tail -f pipeline_T22_T36.log"
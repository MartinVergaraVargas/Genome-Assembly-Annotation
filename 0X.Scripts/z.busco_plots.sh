#!/usr/bin/env bash
# Uso: bash 06_busco_plots.sh
# Espera a que termine el PID del script de BUSCO y genera los gráficos

set -euo pipefail

OUTPUT_DIR="/srv/TFM/PL-iteracion.05/04.BUSCO"

# ── Esperar al proceso ────────────────────────────────────────────────────────

# ── Gráfico individual por cepa ───────────────────────────────────────────────
for CEPA in T16 T22 T36; do
    CEPA_DIR="${OUTPUT_DIR}/${CEPA}_busco"
    mkdir -p "${CEPA_DIR}/busco_figure"

    TMP_DIR=$(mktemp -d)
    cp "${CEPA_DIR}/short_summary"*".txt" "${TMP_DIR}/"

    python3 generate_plot.py -wd "${TMP_DIR}"
    mv "${TMP_DIR}/busco_figure/busco_figure.png" \
       "${CEPA_DIR}/busco_figure/${CEPA}_busco_figure.png"
    rm -rf "${TMP_DIR}"

    echo "  → ${CEPA}: ${CEPA_DIR}/busco_figure/${CEPA}_busco_figure.png"
done

# ── Gráfico comparativo ───────────────────────────────────────────────────────
COMPARATIVE_DIR="${OUTPUT_DIR}/comparative"
mkdir -p "${COMPARATIVE_DIR}"

for CEPA in T16 T22 T36; do
    cp "${OUTPUT_DIR}/${CEPA}_busco/short_summary"*".txt" "${COMPARATIVE_DIR}/"
done

python3 generate_plot.py -wd "${COMPARATIVE_DIR}"
mv "${COMPARATIVE_DIR}/busco_figure/busco_figure.png" \
   "${COMPARATIVE_DIR}/busco_comparative_T16_T22_T36.png"

echo "  → Comparativo: ${COMPARATIVE_DIR}/busco_comparative_T16_T22_T36.png"
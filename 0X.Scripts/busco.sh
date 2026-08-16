#!/usr/bin/env bash
# Uso: bash 05_busco.sh
# Entorno conda: busco

set -euo pipefail

LINEAGE="/srv/biodata/busco_downloads/lineages/hypocreales_odb12"
INPUT_DIR="/srv/TFM/PL-iteracion.05/03.Pulido_y_filtrado"
OUTPUT_DIR="/srv/TFM/PL-iteracion.05/05.BUSCO"
THREADS=16

mkdir -p "${OUTPUT_DIR}"

for CEPA in T16 T22 T36; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando BUSCO — Cepa: ${CEPA}"

    busco \
        -i "${INPUT_DIR}/${CEPA}/${CEPA}_filtered_3000.fasta" \
        -o "${CEPA}_busco" \
        --out_path "${OUTPUT_DIR}" \
        -l "${LINEAGE}" \
        -m genome \
        -c "${THREADS}" \
        --offline \
        2>&1 | tee -a "${OUTPUT_DIR}/${CEPA}_busco.log"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Finalizado — Cepa: ${CEPA}"
done

echo ""
echo "===== Resumen de las tres cepas ====="
for CEPA in T16 T22 T36; do
    echo ""
    echo "--- ${CEPA} ---"
    cat "${OUTPUT_DIR}/${CEPA}_busco/short_summary"*".txt" 2>/dev/null || \
        echo "  (resumen no encontrado)"
done


# busco \
#     -i /srv/TFM/PL-iteracion.05/04.Funannotate/T36/annotate_misc/genome.proteins.fasta \
#     -o run_busco_test \
#     --out_path /srv/TFM/PL-iteracion.05/04.Funannotate/T36/annotate_misc/ \
#     -l /srv/biodata/busco_downloads/lineages/hypocreales_odb12 \
#     -m proteins \
#     -c 16 \
#     --offline \
#     2>&1 | tail -20
#!/usr/bin/env bash
# =============================================================================
# PIPELINE MAESTRO — Ensamblaje, pulido y anotación de una cepa
#
# Uso:
#   bash pipeline_maestro.sh H5258
#   bash pipeline_maestro.sh H10603
#   nohup bash pipeline_maestro.sh H5258 > pipeline_H5258.log 2>&1 &
#
# Orden de etapas:
#   1. Trimmomatic
#   2. SPAdes
#   3. Pilon (polishing)
#   4. Filtrado de contigs ≥3000 bp (seqkit)
#   5. Funannotate clean → sort → mask
#   6. Funannotate train
#   7. Funannotate predict + InterProScan + BUSCO + Funannotate annotate
# =============================================================================

set -euo pipefail

# ── Argumento obligatorio ─────────────────────────────────────────────────────
CEPA="${1:?Indica la cepa como argumento. Ej: bash pipeline_maestro.sh H5258}"

# ── Configuración global ──────────────────────────────────────────────────────
BASE_DIR="/srv/TFM/PL-iteracion.05"
SCRIPTS_DIR="${BASE_DIR}"
EMAIL="your-email@example.com"
SPECIES="Trichoderma sp."
STRAIN="${CEPA}"
MONITOR_INTERVAL=60    # segundos entre cada muestreo de du

# ── Log maestro ───────────────────────────────────────────────────────────────
MASTER_LOG="${BASE_DIR}/pipeline_${CEPA}_$(date +%Y%m%d_%H%M%S).log"
MONITOR_LOG="${BASE_DIR}/pipeline_${CEPA}_monitor_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "${MASTER_LOG}") 2>&1

# ── Función: timestamp ────────────────────────────────────────────────────────
ts() { date '+%Y-%m-%d %H:%M:%S'; }

# ── Función: correo ───────────────────────────────────────────────────────────
notify() {
    local asunto="$1"
    local cuerpo="$2"
    echo "${cuerpo}" | mail -s "${asunto}" "${EMAIL}" || true
}

# ── Función: convertir bytes a formato human-readable ────────────────────────
bytes_to_human() {
    local bytes="$1"
    if   [[ "${bytes}" -ge 1073741824 ]]; then
        awk "BEGIN {printf \"%.2f GB\", ${bytes}/1073741824}"
    elif [[ "${bytes}" -ge 1048576 ]]; then
        awk "BEGIN {printf \"%.2f MB\", ${bytes}/1048576}"
    elif [[ "${bytes}" -ge 1024 ]]; then
        awk "BEGIN {printf \"%.2f KB\", ${bytes}/1024}"
    else
        echo "${bytes} B"
    fi
}

# ── Función: du seguro sobre una lista de directorios ────────────────────────
du_sum_bytes() {
    local total=0
    local size
    for dir in "$@"; do
        if [[ -d "${dir}" ]]; then
            size=$(du -sb "${dir}" 2>/dev/null | awk '{print $1}')
            total=$(( total + size ))
        fi
    done
    echo "${total}"
}

# =============================================================================
# Monitor de temporales
#
# start_monitor "ETIQUETA" DIR1 DIR2 ...
# stop_monitor   → mata el monitor, reporta pesos en MONITOR_LOG
# =============================================================================

MONITOR_PID=""
MONITOR_STATE_FILE=""
MONITOR_LABEL=""

start_monitor() {
    MONITOR_LABEL="$1"
    shift
    local dirs=("$@")

    MONITOR_STATE_FILE=$(mktemp /tmp/monitor_${CEPA}_XXXXXX)
    echo "MAX 0" > "${MONITOR_STATE_FILE}"

    echo "[$(ts)] [MONITOR] Iniciando monitorización de temporales — ${MONITOR_LABEL}"
    echo "[MONITOR] Directorios vigilados:"
    for d in "${dirs[@]}"; do
        echo "          ${d}"
    done

    local dirs_str="${dirs[*]}"
    local interval="${MONITOR_INTERVAL}"
    local state_file="${MONITOR_STATE_FILE}"

    bash -c "
        max_bytes=0
        while true; do
            total=0
            for dir in ${dirs_str}; do
                if [[ -d \"\${dir}\" ]]; then
                    size=\$(du -sb \"\${dir}\" 2>/dev/null | awk '{print \$1}')
                    total=\$(( total + size ))
                fi
            done
            if [[ \${total} -gt \${max_bytes} ]]; then
                max_bytes=\${total}
            fi
            {
                echo \"MAX \${max_bytes}\"
                echo \"LAST \${total}\"
                echo \"TS \$(date '+%Y-%m-%d %H:%M:%S')\"
            } > \"${state_file}\"
            sleep ${interval}
        done
    " &

    MONITOR_PID=$!
    echo "[$(ts)] [MONITOR] PID del monitor: ${MONITOR_PID}"
}

stop_monitor() {
    if [[ -z "${MONITOR_PID}" ]]; then
        return 0
    fi

    kill "${MONITOR_PID}" 2>/dev/null || true
    wait "${MONITOR_PID}" 2>/dev/null || true

    local max_bytes=0
    local last_bytes=0
    local last_ts="desconocido"

    if [[ -f "${MONITOR_STATE_FILE}" ]]; then
        max_bytes=$(grep  "^MAX "  "${MONITOR_STATE_FILE}" | awk '{print $2}')
        last_bytes=$(grep "^LAST " "${MONITOR_STATE_FILE}" | awk '{print $2}')
        last_ts=$(grep    "^TS "   "${MONITOR_STATE_FILE}" | cut -d' ' -f2-3)
        rm -f "${MONITOR_STATE_FILE}"
    fi

    local max_human last_human
    max_human=$(bytes_to_human "${max_bytes}")
    last_human=$(bytes_to_human "${last_bytes}")

    {
        echo ""
        echo "[$(ts)] [MONITOR] ── Reporte de temporales: ${MONITOR_LABEL} ──"
        echo "[MONITOR]   Peso máximo registrado : ${max_human}  (${max_bytes} bytes)"
        echo "[MONITOR]   Peso final (snapshot)  : ${last_human}  (${last_bytes} bytes)"
        echo "[MONITOR]   Última lectura a       : ${last_ts}"
        echo "[MONITOR]   Intervalo de muestreo  : ${MONITOR_INTERVAL}s"
        echo ""
    } >> "${MONITOR_LOG}"

    MONITOR_PID=""
    MONITOR_STATE_FILE=""
}

# =============================================================================
# INICIO
# =============================================================================
echo "============================================================"
echo "  PIPELINE MAESTRO — Cepa: ${CEPA}"
echo "  Inicio: $(ts)"
echo "  Log:    ${MASTER_LOG}"
echo "============================================================"

notify "[PIPELINE INICIO] ${CEPA}" \
    "Pipeline iniciado para ${CEPA} a las $(ts).\nLog: ${MASTER_LOG}"

# =============================================================================
# ETAPA 1 — Trimmomatic
# Outputs que se conservan:
#   - {CEPA}_1_paired.fastq.gz  → input SPAdes y Pilon
#   - {CEPA}_2_paired.fastq.gz  → input SPAdes y Pilon
#   - {CEPA}_1_unpaired.fastq.gz → input SPAdes (-s)
# Se borra tras el monitor:
#   - {CEPA}_trimlog.txt  (log línea por línea, muy grande, ya está en el log maestro)
#   - {CEPA}_2_unpaired.fastq.gz (no se usa en ninguna etapa posterior)
# =============================================================================
# echo ""
# echo "------------------------------------------------------------"
# echo "  ETAPA 1 — Trimmomatic  |  $(ts)"
# echo "------------------------------------------------------------"

# start_monitor "Trimmomatic" \
#     "${BASE_DIR}/01.Trimmomatic/${CEPA}"

# bash "${SCRIPTS_DIR}/01_trimmomatic.sh" "${CEPA}"

# stop_monitor

# echo "[$(ts)] [CLEANUP] Etapa 1 — borrando temporales de Trimmomatic..."
# rm -f  "${BASE_DIR}/01.Trimmomatic/${CEPA}/${CEPA}_trimlog.txt"
# rm -f  "${BASE_DIR}/01.Trimmomatic/${CEPA}/${CEPA}_2_unpaired.fastq.gz"
# echo "[$(ts)] [CLEANUP] Etapa 1 completada."

# echo "[$(ts)] ETAPA 1 completada."
# notify "[ETAPA 1 OK] Trimmomatic — ${CEPA}" \
#     "Trimmomatic completado para ${CEPA} a las $(ts).\nSalida: ${BASE_DIR}/01.Trimmomatic/${CEPA}/"

# # =============================================================================
# # ETAPA 2 — SPAdes
# # Outputs que se conservan:
# #   - scaffolds.fasta  → input Pilon (etapa 3)
# # Se borra tras el monitor:
# #   - K*/   grafos de k-mers (varios GB, no necesarios tras el ensamblaje)
# #   - tmp/  directorio temporal de SPAdes
# #   - misc/ correcciones de errores de SPAdes
# # =============================================================================
# echo ""
# echo "------------------------------------------------------------"
# echo "  ETAPA 2 — SPAdes  |  $(ts)"
# echo "------------------------------------------------------------"

# start_monitor "SPAdes" \
#     "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}"

# bash "${SCRIPTS_DIR}/02_spades.sh" "${CEPA}"

# stop_monitor

# echo "[$(ts)] [CLEANUP] Etapa 2 — borrando grafos de k-mers y temporales de SPAdes..."
# rm -rf "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/K"*/
# rm -rf "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/tmp/"
# rm -rf "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/misc/"
# echo "[$(ts)] [CLEANUP] Etapa 2 completada."

# echo "[$(ts)] ETAPA 2 completada."
# notify "[ETAPA 2 OK] SPAdes — ${CEPA}" \
#     "SPAdes completado para ${CEPA} a las $(ts).\nEnsamblaje en: ${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/scaffolds.fasta"

# # =============================================================================
# # ETAPA 3 — Pilon (polishing iterativo)
# # Outputs que se conservan:
# #   - {CEPA}_assembly_final.fasta  → input filtrado (etapa 4)
# # Se borra tras el monitor:
# #   - {CEPA}_scaffolds_initial.fasta  (copia redundante de scaffolds.fasta)
# #   - round_1/ ... round_{N-1}/       (rondas intermedias; se conserva solo la última)
# #   - Índices BWA junto a scaffolds.fasta en el directorio de SPAdes
# #   - Todo el directorio 02.SPAdes_Assembly/{CEPA}/ (scaffolds.fasta ya no se necesita)
# #   - {CEPA}_1_unpaired.fastq.gz de Trimmomatic (solo se usaba en SPAdes -s, ya terminó)
# # =============================================================================
# echo ""
# echo "------------------------------------------------------------"
# echo "  ETAPA 3 — Pilon  |  $(ts)"
# echo "------------------------------------------------------------"

# start_monitor "Pilon" \
#     "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}" \
#     "${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}"

# bash "${SCRIPTS_DIR}/03_pulido.sh" "${CEPA}"

# stop_monitor

# echo "[$(ts)] [CLEANUP] Etapa 3 — borrando temporales de Pilon..."

# # Índices BWA que quedaron junto a scaffolds.fasta
# rm -f "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/scaffolds.fasta".amb \
#       "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/scaffolds.fasta".ann \
#       "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/scaffolds.fasta".bwt \
#       "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/scaffolds.fasta".pac \
#       "${BASE_DIR}/02.SPAdes_Assembly/${CEPA}/scaffolds.fasta".sa

# # Directorio completo de SPAdes (scaffolds.fasta ya no se necesita)


# # Rondas intermedias de Pilon: conservar solo la última
# PILON_DIR="${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}"
# LAST_ROUND=$(ls -d "${PILON_DIR}/round_"*/ 2>/dev/null | sort -V | tail -1)
# if [[ -n "${LAST_ROUND}" ]]; then
#     for round_dir in "${PILON_DIR}/round_"*/; do
#         [[ "${round_dir%/}" != "${LAST_ROUND%/}" ]] && rm -rf "${round_dir}"
#     done
# fi

# # Las lecturas sin pareja ya no se usan a partir de aquí
# rm -f "${BASE_DIR}/01.Trimmomatic/${CEPA}/${CEPA}_1_unpaired.fastq.gz"

# echo "[$(ts)] [CLEANUP] Etapa 3 completada."

# echo "[$(ts)] ETAPA 3 completada."
# notify "[ETAPA 3 OK] Pilon — ${CEPA}" \
#     "Pilon completado para ${CEPA} a las $(ts).\nEnsamblaje final: ${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}/${CEPA}_assembly_final.fasta"

# # =============================================================================
# # ETAPA 4 — Filtrado seqkit (≥3000 bp)
# # Outputs que se conservan:
# #   - {CEPA}_filtered_3000.fasta  → input funannotate (etapa 5)
# # Se borra tras el monitor:
# #   - {CEPA}_assembly_final.fasta  (ya filtrado, no se necesita más)
# #   - La última round_N/ de Pilon  (ya se tiene el assembly_final copiado)
# # =============================================================================
# echo ""
# echo "------------------------------------------------------------"
# echo "  ETAPA 4 — Filtrado seqkit (≥3000 bp)  |  $(ts)"
# echo "------------------------------------------------------------"

# start_monitor "Filtrado-seqkit" \
#     "${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}"

# bash "${SCRIPTS_DIR}/04_filtrado.sh" "${CEPA}"

# stop_monitor

# echo "[$(ts)] [CLEANUP] Etapa 4 — borrando ensamblaje pre-filtro y última ronda de Pilon..."
# rm -f  "${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}/${CEPA}_assembly_final.fasta"
# rm -rf "${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}/round_"*/
# echo "[$(ts)] [CLEANUP] Etapa 4 completada."

# echo "[$(ts)] ETAPA 4 completada."
# notify "[ETAPA 4 OK] Filtrado — ${CEPA}" \
#     "Filtrado de contigs completado para ${CEPA} a las $(ts).\nFASTA filtrado: ${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}/${CEPA}_filtered_3000.fasta"

# # =============================================================================
# # ETAPA 5 — Funannotate clean → sort → mask
# # Outputs que se conservan:
# #   - {CEPA}_masked.fasta  → input train (etapa 6) y predict (etapa 7)
# # Se borra tras el monitor:
# #   - {CEPA}_clean.fasta   (intermedio)
# #   - {CEPA}_sorted.fasta  (intermedio)
# #   - Carpetas temporales de RepeatMasker (*.fasta.???)
# #   - {CEPA}_filtered_3000.fasta de la etapa 4 (ya procesado por funannotate)
# # =============================================================================
# echo ""
# echo "------------------------------------------------------------"
# echo "  ETAPA 5 — Funannotate clean/sort/mask  |  $(ts)"
# echo "------------------------------------------------------------"

# start_monitor "Funannotate-clean-sort-mask" \
#     "${BASE_DIR}/04.Funannotate/${CEPA}"

# python3 "${SCRIPTS_DIR}/fun_initcleansortmask.py" "${CEPA}"

# stop_monitor

# echo "[$(ts)] [CLEANUP] Etapa 5 — borrando intermedios de clean/sort y temporales de RepeatMasker..."
# rm -f  "${BASE_DIR}/04.Funannotate/${CEPA}/${CEPA}_clean.fasta"
# rm -f  "${BASE_DIR}/04.Funannotate/${CEPA}/${CEPA}_sorted.fasta"
# rm -f  "${BASE_DIR}/03.Pulido_y_filtrado/${CEPA}/${CEPA}_filtered_3000.fasta"
# # Carpetas temporales de RepeatMasker (nombre: *.fasta seguido de sufijo aleatorio)
# find "${BASE_DIR}/04.Funannotate/${CEPA}/" -maxdepth 1 \
#      -name "*.fasta.*" -type d -exec rm -rf {} + 2>/dev/null || true
# echo "[$(ts)] [CLEANUP] Etapa 5 completada."

# echo "[$(ts)] ETAPA 5 completada."
# notify "[ETAPA 5 OK] Funannotate clean/sort/mask — ${CEPA}" \
#     "clean → sort → mask completados para ${CEPA} a las $(ts).\nGenoma enmascarado: ${BASE_DIR}/04.Funannotate/${CEPA}/${CEPA}_masked.fasta"

# =============================================================================
# ETAPA 6 — Funannotate train
# Outputs que se conservan:
#   - training/  completo  → funannotate predict lo necesita (etapa 7)
# Se borra tras el monitor:
#   - trinity_out_dir/ dentro de DIR_FUNANN (Trinity escribe ahí tras el os.chdir
#     añadido en fun_train.py; se borra la copia de la raíz por si acaso)
#   - training/*.bam  alineamientos intermedios de HISAT2 (pesados, no los necesita predict)
# =============================================================================

# ── Activar entorno funannotate (etapas 6 y 7) ───────────────────────────────
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate funannotate

echo ""
echo "------------------------------------------------------------"
echo "  ETAPA 6 — Funannotate train  |  $(ts)"
echo "------------------------------------------------------------"

start_monitor "Funannotate-train" \
    "${BASE_DIR}/04.Funannotate/${CEPA}" \
    "${BASE_DIR}"

python3 "${SCRIPTS_DIR}/fun_train.py" "${CEPA}"

stop_monitor

echo "[$(ts)] [CLEANUP] Etapa 6 — borrando trinity_out_dir y BAMs de HISAT2..."
# trinity_out_dir: puede estar en DIR_FUNANN (tras el os.chdir) o en la raíz (sin él)
rm -rf "${BASE_DIR}/04.Funannotate/${CEPA}/trinity_out_dir/"
rm -rf "${BASE_DIR}/trinity_out_dir/"
# BAMs de HISAT2 en training/ (pesados, predict solo necesita el modelo .gtf / .db)
rm -f  "${BASE_DIR}/04.Funannotate/${CEPA}/training/"*.bam
rm -f  "${BASE_DIR}/04.Funannotate/${CEPA}/training/"*.bam.bai
echo "[$(ts)] [CLEANUP] Etapa 6 completada."

echo "[$(ts)] ETAPA 6 completada."
notify "[ETAPA 6 OK] Funannotate train — ${CEPA}" \
    "Funannotate train completado para ${CEPA} a las $(ts).\nModelo de entrenamiento en: ${BASE_DIR}/04.Funannotate/${CEPA}/training/"

# =============================================================================
# ETAPA 7 — predict + InterProScan + BUSCO + annotate
# Outputs que se conservan:
#   - annotate_results/  completo  → resultado final del pipeline
#   - predict_results/   completo  → proteínas y GFF predichos (útil conservar)
#   - interproscan_{CEPA}.xml      → por si hay que re-anotar
# Se borra tras el monitor:
#   - ipr_temp/                    (temporales de InterProScan)
#   - annotate_misc/run_busco_test/ (resultado BUSCO ya copiado a run_busco/)
#   - Las lecturas paired de Trimmomatic (ya no se necesitan)
#   - El genoma enmascarado (ya está en annotate_results/ si funannotate lo copia;
#     se deja comentado por precaución — descomenta si confirmas que está en results)
# =============================================================================
echo ""
echo "------------------------------------------------------------"
echo "  ETAPA 7 — predict / InterProScan / BUSCO / annotate  |  $(ts)"
echo "------------------------------------------------------------"

start_monitor "Funannotate-predict-IPR-BUSCO-annotate" \
    "${BASE_DIR}/04.Funannotate/${CEPA}"

python3 "${SCRIPTS_DIR}/predict_iprscan_busco_annotate.py" \
    "${CEPA}" "${SPECIES}" "${STRAIN}"

stop_monitor

echo "[$(ts)] [CLEANUP] Etapa 7 — borrando temporales de IPR, BUSCO y lecturas Trimmomatic..."
rm -rf "${BASE_DIR}/04.Funannotate/${CEPA}/ipr_temp/"
rm -rf "${BASE_DIR}/04.Funannotate/${CEPA}/annotate_misc/run_busco_test/"
# Lecturas paired de Trimmomatic: ya no se necesitan en ninguna etapa posterior
rm -f  "${BASE_DIR}/01.Trimmomatic/${CEPA}/${CEPA}_1_paired.fastq.gz"
rm -f  "${BASE_DIR}/01.Trimmomatic/${CEPA}/${CEPA}_2_paired.fastq.gz"
# Opcional: borrar el genoma enmascarado si ya está referenciado en annotate_results
# rm -f "${BASE_DIR}/04.Funannotate/${CEPA}/${CEPA}_masked.fasta"
echo "[$(ts)] [CLEANUP] Etapa 7 completada."

echo "[$(ts)] ETAPA 7 completada."
notify "[ETAPA 7 OK] predict/IPR/BUSCO/annotate — ${CEPA}" \
    "Etapa final completada para ${CEPA} a las $(ts).\nResultados de anotación: ${BASE_DIR}/04.Funannotate/${CEPA}/annotate_results/"

# =============================================================================
# FIN
# =============================================================================
echo ""
echo "============================================================"
echo "  PIPELINE COMPLETO — Cepa: ${CEPA}"
echo "  Fin: $(ts)"
echo "  Log completo: ${MASTER_LOG}"
echo "============================================================"

notify "[PIPELINE COMPLETO] ${CEPA}" \
    "¡Pipeline finalizado con éxito para ${CEPA}!\n\nFin: $(ts)\nResultados: ${BASE_DIR}/04.Funannotate/${CEPA}/annotate_results/\nLog completo: ${MASTER_LOG}"
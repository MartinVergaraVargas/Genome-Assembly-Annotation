#!/usr/bin/env bash
# =============================================================================
# cleanup_pipeline.sh
# Limpieza de archivos intermedios del pipeline TFM (Funannotate / BUSCO / etc.)
#
# USO:
#   ./cleanup_pipeline.sh --dry-run    # Solo muestra lo que SE BORRARÍA (seguro)
#   ./cleanup_pipeline.sh --run        # Ejecuta el borrado real
#
# Ajusta BASE_DIR si ejecutas el script desde otro lugar.
# =============================================================================

set -euo pipefail

BASE_DIR="/srv/TFM/PL-iteracion.05"
DRY_RUN=true
TOTAL_FILES=0
LOG_FILE="${BASE_DIR}/cleanup_$(date +%Y%m%d_%H%M%S).log"

# --------------------------------------------------------------------------
# Parseo de argumentos
# --------------------------------------------------------------------------
if [[ $# -eq 0 ]]; then
    echo "ERROR: Especifica --dry-run o --run"
    echo "  Ejemplo: $0 --dry-run"
    exit 1
fi

case "$1" in
    --dry-run) DRY_RUN=true  ;;
    --run)     DRY_RUN=false ;;
    *) echo "Argumento desconocido: $1. Usa --dry-run o --run"; exit 1 ;;
esac

# --------------------------------------------------------------------------
# Función auxiliar
# --------------------------------------------------------------------------
delete_pattern() {
    local description="$1"
    local find_cmd="$2"      # el comando find como string (se evalúa)
    local count

    # Contar archivos que matchean
    count=$(eval "$find_cmd" 2>/dev/null | wc -l)
    TOTAL_FILES=$((TOTAL_FILES + count))

    echo ""
    echo ">>> $description"
    echo "    Archivos encontrados: $count"

    if $DRY_RUN; then
        eval "$find_cmd" 2>/dev/null | head -5 | sed 's/^/    [DRY] /'
        [[ $count -gt 5 ]] && echo "    [DRY] ... y $((count - 5)) más"
    else
        echo "    Borrando..." | tee -a "$LOG_FILE"
        eval "$find_cmd" 2>/dev/null | tee -a "$LOG_FILE" | xargs -r rm -f
        echo "    ✓ $count archivos eliminados" | tee -a "$LOG_FILE"
    fi
}

delete_dir() {
    local description="$1"
    local dir_path="$2"

    if [[ -d "$dir_path" ]]; then
        local count
        count=$(find "$dir_path" -type f 2>/dev/null | wc -l)
        TOTAL_FILES=$((TOTAL_FILES + count))
        echo ""
        echo ">>> $description"
        echo "    Directorio: $dir_path"
        echo "    Archivos en su interior: $count"
        if $DRY_RUN; then
            echo "    [DRY] rm -rf $dir_path"
        else
            rm -rf "$dir_path"
            echo "    ✓ Directorio eliminado" | tee -a "$LOG_FILE"
        fi
    else
        echo ""
        echo ">>> $description"
        echo "    (no encontrado, omitiendo): $dir_path"
    fi
}

# --------------------------------------------------------------------------
# Cabecera
# --------------------------------------------------------------------------
echo "============================================================"
echo " cleanup_pipeline.sh"
echo " BASE_DIR : $BASE_DIR"
echo " MODO     : $( $DRY_RUN && echo 'DRY-RUN (solo lectura)' || echo '*** BORRADO REAL ***' )"
echo " Fecha    : $(date)"
echo "============================================================"

# ==========================================================================
# BLOQUE 1 — FUNANNOTATE: archivos intermedios de Trinity (el mayor peso)
# Dentro de 04.Funannotate/*/training/ hay decenas de miles de archivos por
# locus generados durante el paso `funannotate train`.
# El resultado consolidado ya está en trinity.fasta y trinity.alignments.bam.
# ==========================================================================

echo ""
echo "=== BLOQUE 1: Intermedios de Trinity (Funannotate train) ==="

# Alineamientos SAM por locus (uno por ventana del genoma)
delete_pattern \
    "Archivos .sam de Trinity por locus" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.sam'"

# Archivos de reads asignados a cada locus
delete_pattern \
    "Archivos trinity.reads por locus" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.trinity.reads'"

# Ensamblajes Trinity parciales por locus (ya consolidados en trinity.fasta)
delete_pattern \
    "Ensamblajes Trinity parciales por locus (*.trinity.reads.out.Trinity.fasta)" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.trinity.reads.out.Trinity.fasta'"

# Archivos de cobertura/fragmentos de HISAT2 normalizados (intermedios de Trinity-GG)
delete_pattern \
    "Archivos .wig de cobertura (intermedios HISAT2/Trinity)" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.wig'"

delete_pattern \
    "Archivos frag_coords / read_coords (intermedios Trinity)" \
    "find '${BASE_DIR}/04.Funannotate' -type f \( -name '*.frag_coords' -o -name '*.read_coords' -o -name '*.read_coords.sort_by_readname' \)"

# ==========================================================================
# BLOQUE 2 — FUNANNOTATE: archivos intermedios de EVM
# Funannotate divide el genoma en particiones para EVM; cada una genera
# evm.out y evm.out.log. El resultado final ya está consolidado en el .gff3.
# ==========================================================================

echo ""
echo "=== BLOQUE 2: Intermedios de EvidenceModeler (EVM) ==="

delete_pattern \
    "Archivos evm.out por partición (intermedios EVM)" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name 'evm.out'"

delete_pattern \
    "Logs evm.out.log por partición" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name 'evm.out.log'"

# ==========================================================================
# BLOQUE 3 — FUNANNOTATE: salidas crudas fragmentadas de BLAST/HMMER
# funannotate predict divide las proteínas en chunks y lanza BLAST/hmmer
# en paralelo; cada chunk genera un .raw.out, .raw.domtblout.out, etc.
# Los resultados finales ya están integrados en el .gff3 de predicción.
# ==========================================================================

echo ""
echo "=== BLOQUE 3: Salidas crudas fragmentadas BLAST/HMMER (predict_misc) ==="

delete_pattern \
    "Archivos .raw.out de BLAST/HMMER por chunk" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.raw.out'"

delete_pattern \
    "Archivos .raw.domtblout.out por chunk" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.raw.domtblout.out'"

delete_pattern \
    "Archivos .blast.raw.out por chunk" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.blast.raw.out'"

delete_pattern \
    "Archivos .raw.align.out por chunk" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.raw.align.out'"

# ==========================================================================
# BLOQUE 4 — FUNANNOTATE: checkpoints .ok y archivos EPA (.jplace)
# Los .ok son flags de control interno de Funannotate, no datos.
# Los .jplace son colocaciones filogenéticas de EPA-ng para BUSCO/SignalP,
# solo necesarios si se reanuda el pipeline (ya terminado).
# ==========================================================================

echo ""
echo "=== BLOQUE 4: Checkpoints .ok y resultados EPA (.jplace) de Funannotate ==="

delete_pattern \
    "Archivos de checkpoint .ok (flags internos Funannotate)" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.ok'"

delete_pattern \
    "Archivos .jplace de EPA-ng (colocaciones filogenéticas intermedias)" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name 'epa_result.jplace'"

# ==========================================================================
# BLOQUE 5 — FUNANNOTATE: índices HISAT2 (.ht2)
# Se pueden regenerar con `hisat2-build genome.fasta hisat2.genome` en minutos.
# Comenta este bloque si prefieres conservarlos para no regenerarlos.
# ==========================================================================

echo ""
echo "=== BLOQUE 5: Índices HISAT2 (.ht2) — regenerables ==="

delete_pattern \
    "Índices HISAT2 (*.ht2) — se regeneran con hisat2-build" \
    "find '${BASE_DIR}/04.Funannotate' -type f -name '*.ht2'"

# ==========================================================================
# BLOQUE 6 — BUSCO: secuencias individuales por gen
# Las carpetas busco_sequences/ contienen un .faa y .gff por cada BUSCO.
# El resumen estadístico ya está en short_summary*.txt.
# CONSERVA este bloque comentado si planeas hacer filogenómica con estos genes.
# ==========================================================================

echo ""
echo "=== BLOQUE 6: Secuencias BUSCO individuales (.faa/.gff por gen) ==="
echo "    NOTA: Comenta este bloque si necesitas estas secuencias para filogenómica."

delete_pattern \
    "Secuencias BUSCO por gen (.faa)" \
    "find '${BASE_DIR}/04.BUSCO' -path '*/busco_sequences/*' -name '*.faa'"

delete_pattern \
    "Anotaciones BUSCO por gen (.gff)" \
    "find '${BASE_DIR}/04.BUSCO' -path '*/busco_sequences/*' -name '*.gff'"

# ==========================================================================
# BLOQUE 7 — FASTQ sin comprimir y archivos SRA crudos
# ==========================================================================

echo ""
echo "=== BLOQUE 7: Archivos sin comprimir y SRA crudos ==="

# Fastq sin comprimir en test/ (ya existe la versión .gz o se puede regenerar)
delete_pattern \
    "Fastq sin comprimir en SRA-seq/test/" \
    "find '${BASE_DIR}/00.Archivos_principales/SRA-seq/test' -type f -name '*.fastq'"

# Archivo .sra crudo (ya descargado y convertido a fastq)
delete_pattern \
    "Archivo .sra crudo en SRA-seq/test/" \
    "find '${BASE_DIR}/00.Archivos_principales/SRA-seq/test' -type f -name '*.sra'"

# ==========================================================================
# BLOQUE 8 — Carpetas Respaldo/ (duplicados de fastq.gz)
# Son copias exactas de los .fastq.gz del directorio padre. Si tienes los
# originales seguros (o ya en SRA), se pueden borrar.
# ==========================================================================

echo ""
echo "=== BLOQUE 8: Carpetas Respaldo/ (duplicados de fastq.gz) ==="

for cepa in T16 T22 T36; do
    delete_dir \
        "Respaldo fastq.gz duplicados — ${cepa}" \
        "${BASE_DIR}/00.Archivos_principales/Secuencias_Illumina/${cepa}/Respaldo"
done

# ==========================================================================
# BLOQUE 9 — ERRORES_intentos_fallidos/ (intentos fallidos completos)
# 44 GB de datos de runs que no salieron bien. Si el pipeline ya terminó
# correctamente, este directorio no tiene utilidad.
# ==========================================================================

echo ""
echo "=== BLOQUE 9: Directorio ERRORES_intentos_fallidos/ (44 GB) ==="

delete_dir \
    "Datos de intentos fallidos del pipeline" \
    "${BASE_DIR}/ERRORES_intentos_fallidos"

# ==========================================================================
# BLOQUE 10 — Índices BLAST en 03.Pulido_y_filtrado/T36/
# Los archivos .ndb .nhr .nin .njs .not .nsq .ntf .nto .fai son índices
# regenerables con `makeblastdb` y `samtools faidx`.
# ==========================================================================

echo ""
echo "=== BLOQUE 10: Índices BLAST y .fai en 03.Pulido_y_filtrado/ ==="

delete_pattern \
    "Índices BLAST (makeblastdb) en 03.Pulido_y_filtrado" \
    "find '${BASE_DIR}/03.Pulido_y_filtrado' -type f \( -name '*.ndb' -o -name '*.nhr' -o -name '*.nin' -o -name '*.njs' -o -name '*.not' -o -name '*.nsq' -o -name '*.ntf' -o -name '*.nto' \)"

delete_pattern \
    "Índices FASTA samtools (.fai) en 03.Pulido_y_filtrado" \
    "find '${BASE_DIR}/03.Pulido_y_filtrado' -type f -name '*.fai'"

# ==========================================================================
# BLOQUE 11 — Archivos .zip de FastQC (reportes ya en .html)
# El .html ya tiene toda la información visual. El .zip solo es necesario
# si usas MultiQC o quieres re-parsear los datos en bruto.
# ==========================================================================

echo ""
echo "=== BLOQUE 11: Archivos .zip de FastQC (contenido ya en .html) ==="
echo "    NOTA: Comenta este bloque si usas MultiQC (necesita los .zip)."

delete_pattern \
    "Archivos .zip de FastQC" \
    "find '${BASE_DIR}/00.Archivos_principales/Secuencias_Illumina' -type f -name '*_fastqc.zip'"

# ==========================================================================
# RESUMEN FINAL
# ==========================================================================

echo ""
echo "============================================================"
echo " RESUMEN"
echo " Total de archivos afectados : $TOTAL_FILES"
if $DRY_RUN; then
    echo " MODO DRY-RUN — ningún archivo fue borrado."
    echo " Para ejecutar el borrado real:"
    echo "   $0 --run"
else
    echo " Borrado completado. Log guardado en:"
    echo "   $LOG_FILE"
fi
echo "============================================================"
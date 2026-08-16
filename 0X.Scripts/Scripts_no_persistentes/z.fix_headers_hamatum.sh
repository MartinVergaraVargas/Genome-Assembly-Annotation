#!/bin/bash
SRA="/srv/TFM/PL-iteracion.05/00.Archivos_principales/SRA-seq/T_hamatum"

fix_read() {
    SRR=$1
    MATE=$2
    SUFFIX=$3
    echo ">>> Procesando ${SRR}_${MATE}"
    zcat ${SRA}/${SRR}_${MATE}.fastq.gz | \
        awk -v s="$SUFFIX" '{if(NR%4==1) print $0"/"s; else print}' | \
        gzip > ${SRA}/${SRR}_${MATE}_fixed.fastq.gz
    echo "  ${SRR}_${MATE} listo"
}

export -f fix_read
export SRA

# Lanzar los 6 archivos en paralelo (3 SRR x 2 mates)
parallel -j 6 fix_read {1} {2} {3} ::: SRR1975571 SRR1975598 SRR1975614 ::: 1 2 :::+ 1 2 1 2 1 2
echo "✓ Todos los headers corregidos"
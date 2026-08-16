BASE_DIR="/srv/TFM/PL-iteracion.05"
REF="/srv/TFM/PL-iteracion.05/00.Archivos_principales/Referencias/Trigam1_AssemblyScaffolds.fasta.gz"  # ajusta la ruta


quast.py \
    "${BASE_DIR}/03.Pulido_y_filtrado/T36/T36_filtered_3000.fasta" \
    -r "${REF}" \
    --labels "EXF-18242" \
    --eukaryote \
    --fungus \
    --fragmented \
    --min-contig 3000 \
    -t 14 \
    -o "${BASE_DIR}/06.QUAST/Solo_T36_y_gamsii"

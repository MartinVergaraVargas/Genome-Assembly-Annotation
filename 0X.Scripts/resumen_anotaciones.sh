echo -e "Cepa\tGenes_Totales\tTranscritos(ARNm)\tGenes_Anotados\tARNt" > resumen_anotacion.tsv

for cepa in T16 T22 T36; do
    dir="/srv/TFM/PL-iteracion.05/04.Funannotate/$cepa/annotate_results"
    
    # 1. Genes detectados (Totales)
    genes=$(awk '$3=="gene"' "$dir"/Trichoderma*.gff3 | wc -l)
    
    # 2. Transcritos (ARNm)
    mrna=$(awk '$3=="mRNA"' "$dir"/Trichoderma*.gff3 | wc -l)
    
    # 3. Genes anotados funcionalmente (Líneas en annotations.txt menos la cabecera)
    anotados=$(tail -n +2 "$dir"/Trichoderma*.annotations.txt | wc -l)
    
    # 4. ARNs de transferencia
    trnas=$(awk '$3=="tRNA"' "$dir"/Trichoderma*.gff3 | wc -l)
    
    echo -e "$cepa\t$genes\t$mrna\t$anotados\t$trnas" >> resumen_anotacion.tsv
done

cat resumen_anotacion.tsv

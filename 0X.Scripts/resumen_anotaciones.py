#!/usr/bin/env python3
import json
import csv
import glob
import os

# 1. Definición del mapeo de encabezados (Nombre columna CSV : Ruta de claves en el JSON)
# Esto mapea de forma plana la estructura jerárquica del JSON.
MAPEO_COLUMNAS = {
    # Metadatos
    "Cepa": ["organism"],
    "Comando": ["command"],
    "Software_Version": ["software", "version"],
    "Fecha_Analisis": ["software", "date"],
    
    # Ensamblaje
    "Ensamblaje_Contigs": ["assembly", "num_contigs"],
    "Ensamblaje_Tamaño_bp": ["assembly", "length"],
    "Ensamblaje_Long_Media_bp": ["assembly", "mean_length"],
    "Ensamblaje_N50": ["assembly", "N50"],
    "Ensamblaje_L50": ["assembly", "L50"],
    "Ensamblaje_N90": ["assembly", "N90"],
    "Ensamblaje_L90": ["assembly", "L90"],
    "Ensamblaje_GC_pct": ["assembly", "GC_content"],
    
    # Anotación General
    "Anotacion_Genes": ["annotation", "genes"],
    "Anotacion_Nombres_Comunes": ["annotation", "common_name"],
    "Anotacion_mRNAs": ["annotation", "mRNA"],
    "Anotacion_tRNAs": ["annotation", "tRNA"],
    "Anotacion_ncRNAs": ["annotation", "ncRNA"],
    "Anotacion_rRNAs": ["annotation", "rRNA"],
    "Anotacion_Long_Media_Gen": ["annotation", "avg_gene_length"],
    
    # Nivel de Transcrito / Exones
    "CDS_Transcritos": ["annotation", "transcript-level", "CDS_transcripts"],
    "CDS_Completos": ["annotation", "transcript-level", "CDS_complete"],
    "CDS_Sin_Start": ["annotation", "transcript-level", "CDS_no-start"],
    "CDS_Sin_Stop": ["annotation", "transcript-level", "CDS_no-stop"],
    "Exones_Totales": ["annotation", "transcript-level", "total_exons"],
    "Exones_CDS_Totales": ["annotation", "transcript-level", "total_cds_exons"],
    "Transcritos_Multi_Exon": ["annotation", "transcript-level", "multiple_exon_transcript"],
    "Transcritos_Mono_Exon": ["annotation", "transcript-level", "single_exon_transcript"],
    "Long_Media_Proteina": ["annotation", "transcript-level", "avg_protein_length"],
    "Exon_Solapamiento_Proteina_pct": ["annotation", "transcript-level", "pct_exon_overlap_protein_evidence"],
    "Exon_Solapamiento_Transcrito_pct": ["annotation", "transcript-level", "pct_exon_overlap_transcript_evidence"],
    
    # Anotación Funcional
    "Funcional_GO": ["annotation", "transcript-level", "functional", "go_terms"],
    "Funcional_InterPro": ["annotation", "transcript-level", "functional", "interproscan"],
    "Funcional_EggNOG": ["annotation", "transcript-level", "functional", "eggnog"],
    "Funcional_Pfam": ["annotation", "transcript-level", "functional", "pfam"],
    "Funcional_CAZyme": ["annotation", "transcript-level", "functional", "cazyme"],
    "Funcional_MEROPS": ["annotation", "transcript-level", "functional", "merops"],
    "Funcional_BUSCO": ["annotation", "transcript-level", "functional", "busco"],
    "Funcional_Secrecion": ["annotation", "transcript-level", "functional", "secretion"]
}

def obtener_valor_anidado(diccionario, lista_claves):
    """Navega de forma segura por un diccionario anidado usando una lista de claves."""
    val = diccionario
    for k in lista_claves:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return ""
    return val if val is not None else ""

def main():
    # Patron de búsqueda adaptado a tus rutas: 04.Funannotate/T16, T22, T36...
    patron_archivos = os.path.join("04.Funannotate", "T*", "annotate_results", "*.stats.json")
    archivos_json = glob.glob(patron_archivos)
    
    if not archivos_json:
        print(f"Error: No se encontraron archivos .stats.json usando el patrón: {patron_archivos}")
        print("Asegúrate de ejecutar este script desde: /srv/TFM/PL-iteracion.05/")
        return

    print(f"Se han detectado {len(archivos_json)} archivos JSON para procesar.")
    
    archivo_salida = "resumen_genomico_detallado.csv"
    columnas_csv = list(MAPEO_COLUMNAS.keys())
    
    # Escritura del CSV final
    with open(archivo_salida, mode="w", newline="", encoding="utf-8") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=columnas_csv)
        writer.writeheader() # Escribe la fila de encabezados recomendados
        
        for ruta_json in sorted(archivos_json):
            print(f"Procesando: {ruta_json} ...")
            try:
                with open(ruta_json, mode="r", encoding="utf-8") as f_json:
                    datos_json = json.load(f_json)
                
                # Construir la fila plana para esta cepa
                fila = {}
                for columna, ruta_claves in MAPEO_COLUMNAS.items():
                    fila[columna] = obtener_valor_anidado(datos_json, ruta_claves)
                
                writer.writerow(fila)
            except Exception as e:
                print(f"Error al procesar el archivo {ruta_json}: {e}")
                
    print(f"\n¡Proceso finalizado con éxito!")
    print(f"Se ha generado el archivo consolidado: {os.path.abspath(archivo_salida)}")

if __name__ == "__main__":
    main()
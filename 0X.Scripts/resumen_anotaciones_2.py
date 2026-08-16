#!/usr/bin/env python3
import json
import csv
import glob
import os

# Definición de las métricas (ahora se convertirán en las FILAS del CSV)
MAPEO_METRICAS = {
    # Metadatos
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
    """Navega de forma segura por el JSON anidado."""
    val = diccionario
    for k in lista_claves:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return ""
    return val if val is not None else ""

def main():
    # Localizar todos los archivos .stats.json
    patron_archivos = os.path.join("04.Funannotate", "T*", "annotate_results", "*.stats.json")
    archivos_json = sorted(glob.glob(patron_archivos))
    
    if not archivos_json:
        print(f"Error: No se encontraron archivos en la ruta especificada.")
        return

    nombres_columnas_cepas = []
    lista_datos_json = []

    # 1. Leer y cargar todos los JSON en memoria primero
    for ruta_json in archivos_json:
        try:
            with open(ruta_json, mode="r", encoding="utf-8") as f_json:
                datos = json.load(f_json)
            
            # Extraer el nombre de la cepa para usarlo como encabezado de columna
            nombre_cepa = datos.get("organism", os.path.basename(ruta_json))
            nombres_columnas_cepas.append(nombre_cepa)
            lista_datos_json.append(datos)
            print(f"Cargados datos de: {nombre_cepa}")
        except Exception as e:
            print(f"Error al leer el archivo {ruta_json}: {e}")

    archivo_salida = "resumen_genomico_transpuesto.csv"
    
    # 2. Generar el CSV con la estructura transpuesta
    with open(archivo_salida, mode="w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        
        # La primera fila contiene los encabezados: "Metrica", Cepa1, Cepa2, Cepa3...
        fila_encabezado = ["Metrica"] + nombres_columnas_cepas
        writer.writerow(fila_encabezado)
        
        # Cada métrica del diccionario se convierte ahora en una fila completa
        for metrica, ruta_claves in MAPEO_METRICAS.items():
            fila_valores = [metrica]
            
            # Extraer el valor de esa métrica para cada una de las cepas cargadas
            for datos_json in lista_datos_json:
                valor = obtener_valor_anidado(datos_json, ruta_claves)
                fila_valores.append(valor)
                
            writer.writerow(fila_valores)

    print(f"\n¡Proceso finalizado!")
    print(f"Se ha generado el archivo transpuesto en: {os.path.abspath(archivo_salida)}")

if __name__ == "__main__":
    main()
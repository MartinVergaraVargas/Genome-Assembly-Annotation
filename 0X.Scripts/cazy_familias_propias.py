#!/usr/bin/env python3
"""
Extrae el conteo de familias CAZy por superfamilia desde los archivos
annotations.txt de funannotate para las cepas propias (T16, T22, T36).

Columnas que genera (igual que la hoja de comparativa):
    Cepa, CAZy, AA, CBM91, CBM92, CBM, CE, EXPN, GH184, GH195, GH, GT, Myosin_motor, PL38, PL

Uso:
    Ejecutar desde /srv/TFM/PL-iteracion.05/
        python3 cazy_familias_propias.py

    O indicar la ruta base como argumento:
        python3 cazy_familias_propias.py /srv/TFM/PL-iteracion.05
"""

import os
import sys
import csv
from collections import defaultdict

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
#BASE_DIR = sys.argv[1] if len(sys.argv) > 1 else "/srv/TFM/PL-iteracion.05"
BASE_DIR="/media/nesus/Respaldos/TFM/Pipeline"
CEPAS    = ["T16", "T22", "T36"]
SALIDA   = os.path.join(BASE_DIR, "cazy_familias_propias.csv")

# Columna 21 (índice 20) en el annotations.txt de funannotate
COL_CAZYME = 20

# Familias individuales que tienen columna propia en la tabla comparativa
FAMILIAS_INDIVIDUALES = ["CBM91", "CBM92", "EXPN", "GH184", "GH195", "Myosin_motor", "PL38"]

# Superfamilias que se cuentan en bloque (todos los genes cuya familia empiece por ese prefijo)
SUPERFAMILIAS = ["AA", "CBM", "CE", "GH", "GT", "PL"]

# ---------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------

def extraer_superfamilia(nombre_familia):
    """Devuelve el prefijo de superfamilia (GH, GT, AA, CBM, CE, PL) de una familia."""
    for sf in SUPERFAMILIAS:
        if nombre_familia.startswith(sf):
            return sf
    return None


def contar_cazy(ruta_annotations):
    """
    Lee el archivo annotations.txt y devuelve un dict con:
      - conteos por superfamilia (GH, GT, AA, CBM, CE, PL)  → nº de genes (no de anotaciones)
      - conteos de familias individuales especiales
      - total CAZy (nº de genes con al menos una anotación CAZy)
    Un gen puede tener varias familias separadas por ';', pero se cuenta UNA VEZ
    por superfamilia (no se duplica si tiene GH43;CBM66 → suma 1 a GH y 1 a CBM).
    """
    conteos_sf   = defaultdict(int)   # superfamilias
    conteos_ind  = defaultdict(int)   # familias individuales con columna propia
    total_cazy   = 0

    with open(ruta_annotations, encoding="utf-8") as f:
        for i, linea in enumerate(f):
            if i == 0:
                continue                       # saltar cabecera
            campos = linea.rstrip("\n").split("\t")
            if len(campos) <= COL_CAZYME:
                continue
            celda = campos[COL_CAZYME].strip()
            if not celda:
                continue

            familias = [x.strip() for x in celda.split(";") if x.strip()]
            total_cazy += 1

            sf_vistas  = set()   # evitar doble conteo por superfamilia en el mismo gen
            ind_vistas = set()   # idem para familias individuales

            for fam in familias:
                # Familias individuales con columna propia
                for fi in FAMILIAS_INDIVIDUALES:
                    if fam == fi and fi not in ind_vistas:
                        conteos_ind[fi] += 1
                        ind_vistas.add(fi)

                # Superfamilias en bloque
                sf = extraer_superfamilia(fam)
                if sf and sf not in sf_vistas:
                    conteos_sf[sf] += 1
                    sf_vistas.add(sf)

    return total_cazy, conteos_sf, conteos_ind


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    filas = []

    for cepa in CEPAS:
        ruta = os.path.join(
            BASE_DIR, "04.Funannotate", cepa, "annotate_results",
            f"Trichoderma_asperellum_{cepa}.annotations.txt"
        )

        if not os.path.isfile(ruta):
            print(f"[AVISO] No se encontró el archivo para {cepa}: {ruta}")
            # Intentar con glob por si el nombre de especie varía
            import glob
            patron = os.path.join(
                BASE_DIR, "04.Funannotate", cepa, "annotate_results", "*.annotations.txt"
            )
            encontrados = glob.glob(patron)
            if encontrados:
                ruta = encontrados[0]
                print(f"         Usando: {ruta}")
            else:
                print(f"         Omitiendo {cepa}.")
                continue

        print(f"Procesando {cepa}: {ruta}")
        total, sf, ind = contar_cazy(ruta)

        fila = {
            "Cepa"        : cepa,
            "CAZy"        : total,
            "AA"          : sf.get("AA", 0),
            "CBM91"       : ind.get("CBM91", 0),
            "CBM92"       : ind.get("CBM92", 0),
            "CBM"         : sf.get("CBM", 0),
            "CE"          : sf.get("CE", 0),
            "EXPN"        : ind.get("EXPN", 0),
            "GH184"       : ind.get("GH184", 0),
            "GH195"       : ind.get("GH195", 0),
            "GH"          : sf.get("GH", 0),
            "GT"          : sf.get("GT", 0),
            "Myosin_motor": ind.get("Myosin_motor", 0),
            "PL38"        : ind.get("PL38", 0),
            "PL"          : sf.get("PL", 0),
        }
        filas.append(fila)
        print(f"  CAZy total: {total}  |  GH:{sf.get('GH',0)}  GT:{sf.get('GT',0)}  "
              f"AA:{sf.get('AA',0)}  CBM:{sf.get('CBM',0)}  CE:{sf.get('CE',0)}  PL:{sf.get('PL',0)}")

    if not filas:
        print("No se procesó ninguna cepa. Revisa las rutas.")
        return

    columnas = ["Cepa","CAZy","AA","CBM91","CBM92","CBM","CE","EXPN","GH184","GH195","GH","GT","Myosin_motor","PL38","PL"]

    with open(SALIDA, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(filas)

    print(f"\nArchivo generado: {SALIDA}")


if __name__ == "__main__":
    main()
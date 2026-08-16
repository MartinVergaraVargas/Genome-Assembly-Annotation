# Pipeline de Ensamblaje y Anotación de Genomas

*[Read in English](README.md)*

Pipeline de ensamblaje genómico y anotación funcional para hongos, desarrollado para un Trabajo Fin de Máster (TFM) sobre *Trichoderma* spp. Toma lecturas Illumina paired-end de ADN y las lleva a través de recorte, ensamblaje de novo, pulido y anotación génica basada en evidencia de RNA-seq, produciendo un GFF3 final con anotaciones funcionales (Pfam, InterPro, CAZymes, MEROPS, términos GO, etc.).

**Estado: v0.1.0 — funcional, no pulido.** Este pipeline procesó las cepas reales (T16, T22, T36, H5258) usadas en la tesis. Es una herramienta de investigación personal que se ha limpiado para publicarla, no un paquete de propósito general listo para producción — ver [Limitaciones conocidas](#limitaciones-conocidas) más abajo.

## Qué hace

Siete etapas, cada una reanudable de forma independiente:

| Etapa | Herramienta(s) | Salida |
|---|---|---|
| 1. Recorte | Trimmomatic (PE) | Lecturas recortadas por adaptadores/calidad |
| 2. Ensamblaje | SPAdes (`--careful`) | Scaffolds borrador |
| 3. Pulido | Pilon (iterativo, mapeo con bwa) | Ensamblaje pulido |
| 4. Filtrado | seqkit | Contigs ≥ longitud mínima |
| 5. Preparación | funannotate clean/sort/mask | Genoma enmascarado (soft-mask) |
| 6. Entrenamiento | funannotate train (Trinity/PASA) | Modelos entrenados con evidencia RNA-seq |
| 7. Predicción + Anotación | funannotate predict, InterProScan, BUSCO, funannotate annotate | GFF3 final anotado |

## Estructura del repositorio

- **`pipeline/`** — el orquestador: un paquete Python pequeño (dirigido por configuración, con checkpoints y reanudable) que ejecuta las 7 etapas de arriba. Es la parte que vale la pena leer si quieres entender el diseño.
- **`0X.Scripts/`** — los scripts originales de bash/Python por etapa que el orquestador reemplazó. Se conservan como referencia; son los que realmente produjeron los resultados de la tesis antes de la reescritura, y algunos scripts auxiliares (conteo de familias CAZy, resúmenes de anotación, gráficos BUSCO) siguen siendo independientes y se usan tal cual.
- **`pipeline_TFM.ipynb`** — notebook exploratorio usado durante el trabajo de tesis.
- **`herramientas.txt`** — los entornos conda usados (ver más abajo).

Las lecturas crudas, archivos intermedios y los conjuntos completos de resultados (cientos de GB) **no** están incluidos en este repositorio — solo código.

## Por qué existe el orquestador

El pipeline original era un conjunto de scripts numerados de bash/Python ejecutados a mano, con un script maestro (`pipeline_maestro.sh`) donde había que comentar/descomentar bloques de etapas entre ejecuciones. Eso funcionaba, pero no tenía lógica real de reanudación (una etapa que quedaba a medias había que diagnosticarla manualmente) y tenía al menos un bug concreto: el script de entrenamiento de RNA-seq usaba siempre el mismo transcriptoma de referencia agrupado para todas las cepas, sin importar cuál se pasara como argumento.

`pipeline/` reemplaza eso con:
- Un esquema de configuración por cepa validado con Pydantic (`pipeline/config.py`) — `rna_reads` es un campo obligatorio sin valor por defecto, precisamente para que ese bug no pueda reaparecer silenciosamente.
- Checkpoints por paso, no solo por etapa (`pipeline/state.py`) — marcadores JSON atómicos, invalidados mediante un hash de los campos de configuración relevantes para ese paso, de modo que reanudar tras un fallo retoma en el subpaso correcto en vez de repetir horas de trabajo.
- `conda run -n <entorno>` en vez de anteponer al PATH, para que los hooks de activación específicos de cada herramienta (p. ej. PASAHOME/AUGUSTUS_CONFIG_PATH de funannotate) realmente se ejecuten.
- Manejo de interrupciones consciente de grupos de procesos, de modo que matar el pipeline también mata los subprocesos hijos que generan herramientas de larga duración como funannotate/InterProScan.
- Reglas de limpieza declarativas post-etapa, condicionadas a que una etapa *posterior* haya terminado, en vez de líneas `rm` puestas a mano.

## Requisitos

El orquestador en sí solo necesita:
```
python >= 3.10
pydantic >= 2
pyyaml
```
(`conda env create -f pipeline/environment.yml`)

Las herramientas bioinformáticas propiamente dichas corren en sus propios entornos conda dedicados, invocados vía `conda run`:

```
trimmomatic, spades, pilon (+ bwa/samtools), seqkit, funannotate, busco
```
más una instalación independiente de InterProScan. Ver `herramientas.txt` para la lista exacta de entornos con la que se ejecutó.

## Uso

```bash
# validar la configuración de una cepa sin ejecutar nada
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --validate-only

# ejecutar el pipeline completo
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml

# reanudar desde una etapa específica (p. ej. tras corregir algo en la etapa 5)
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --from-stage s5_funannotate_prep

# re-ejecutar exactamente una etapa, forzado
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --only s4_filter --force

# ver qué se ejecutaría sin ejecutar nada
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --dry-run

# adoptar una cepa que ya avanzó bajo los scripts bash antiguos
python -m pipeline.cli adopt --config pipeline/configs/example_strain.yaml
```

Copia `pipeline/configs/example_strain.yaml` por cada cepa en vez de editarlo en el sitio cuando tengas más de una cepa en curso.

Ejecutar los tests unitarios (no requieren herramientas bioinformáticas — la maquinaria de reanudación/configuración se prueba con pasos ficticios):
```bash
python -m unittest discover pipeline/tests
```

## Limitaciones conocidas

- Las rutas en `pipeline/config.py` (`base_dir`, `interproscan_sh`) y en los scripts legacy de `0X.Scripts/` tienen por defecto la disposición de la máquina original del proyecto (`/srv/TFM/...`, `/media/nesus/...`). Vas a necesitar ajustarlas para tu propio entorno.
- La integración de `funannotate` con BUSCO tiene un vacío conocido que este pipeline sortea tolerando deliberadamente el fallo de un primer paso de `annotate`, ejecutando BUSCO a mano, e incorporando su tabla antes de un segundo paso (flag de configuración `funannotate_busco_workaround`, activado por defecto). Desactívalo cuando aguas arriba deje de ser necesario.
- El directorio `0X.Scripts/` es la versión previa a la reescritura, conservada como referencia y por algunos scripts de reportes/gráficos que siguen siendo independientes — no se mantiene en paralelo con `pipeline/`.
- Sin CI, sin empaquetado (`pip install`) todavía.

## Licencia

Aún no decidida — agrega un archivo `LICENSE` antes de asumir que esto está abierto para reutilización.

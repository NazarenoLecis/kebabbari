# Kebabbari

Stima operativa dei kebabbari nelle Marche usando dati aperti e replicabili.

Il progetto usa:

- OpenStreetMap/Overpass per individuare i punti kebab;
- ISTAT Demo POSAS per la popolazione comunale;
- ISTAT confini amministrativi per assegnare ogni punto al comune;
- OpenStreetMap per i denominatori dei punti di ristorazione e delle pizzerie.

## Struttura

- `marche_kebab_runner.py`: configurazione e flusso principale.
- `marche_kebab_utils.py`: download dati, parsing, geografia, deduplica e indicatori.
- `marche_kebab_charts.py`: generazione dei grafici PNG.

## Uso

Installa la dipendenza per creare i PNG:

```powershell
py -m pip install -r requirements.txt
```

Modifica le variabili in `marche_kebab_runner.py`, poi esegui:

```powershell
py marche_kebab_runner.py
```

Parametro principale per gli output:

```python
TIPO_OUTPUT = "entrambi"  # "csv", "grafici", oppure "entrambi"
```

## Output

Lo script puo' generare:

- CSV con elenco kebabbari;
- CSV con punti OSM di ristorazione;
- CSV con pizzerie OSM;
- distribuzione per comune, provincia e regione;
- grafici PNG con rapporto kebabbari/popolazione;
- grafici PNG con rapporto kebabbari/ristoranti;
- grafici PNG con rapporto kebabbari/pizzerie.

Gli output sono separati in:

- `output/marche_kebab/file`: CSV e metadati;
- `output/marche_kebab/grafici`: grafici PNG.

Nel repository vengono pubblicati i PNG in `output/marche_kebab/grafici`, mentre CSV e cache locali sono ignorati da Git.

## Nota metodologica

`Kebabbaro` non e' una categoria statistica ufficiale. Il conteggio e' quindi una stima operativa basata su punti OpenStreetMap con riferimenti a kebab, kebap, doner o shawarma.

Il rapporto con i ristoranti usa come denominatore i punti OpenStreetMap con:

- `amenity=restaurant`
- `amenity=fast_food`
- `amenity=food_court`

Il rapporto con le pizzerie usa come denominatore i punti OpenStreetMap con gli stessi valori `amenity` e un riferimento a `pizza` o `pizzeria` in `cuisine`, `name`, `brand` o `operator`.

Le fonti e la dicitura `Elaborazione di Nazareno Lecis` sono riportate nei grafici generati.

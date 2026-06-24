# Kebabbari

Stima operativa dei kebabbari nelle Marche usando dati aperti e replicabili.

Il progetto usa:

- OpenStreetMap/Overpass per individuare i punti kebab;
- ISTAT Demo POSAS per la popolazione comunale;
- ISTAT confini amministrativi per assegnare ogni punto al comune;
- OpenStreetMap per il denominatore dei punti di ristorazione.

## Struttura

- `marche_kebab_runner.py`: configurazione e flusso principale.
- `marche_kebab_utils.py`: download dati, parsing, geografia, deduplica e indicatori.
- `marche_kebab_charts.py`: generazione dei grafici SVG.

## Uso

Modifica le variabili in `marche_kebab_runner.py`, poi esegui:

```powershell
py marche_kebab_runner.py
```

Parametro principale per gli output:

```python
TIPO_OUTPUT = "entrambi"  # "csv", "grafici", oppure "entrambi"
```

La serie storica provinciale e' configurata qui:

```python
GENERA_SERIE_STORICA = True
ANNI_SERIE_STORICA = list(range(ANNO_ISTAT - 24, ANNO_ISTAT + 1))
```

## Output

Lo script puo' generare:

- CSV con elenco kebabbari;
- CSV con punti OSM di ristorazione;
- distribuzione per comune, provincia e regione;
- grafici SVG con rapporto kebabbari/popolazione;
- grafici SVG con rapporto kebabbari/ristoranti.
- grafici SVG di serie storica provinciale.

Nel repository vengono pubblicati gli SVG in `output/`, mentre CSV e cache locali sono ignorati da Git.

## Nota metodologica

`Kebabbaro` non e' una categoria statistica ufficiale. Il conteggio e' quindi una stima operativa basata su punti OpenStreetMap con riferimenti a kebab, kebap, doner o shawarma.

Il rapporto con i ristoranti usa come denominatore i punti OpenStreetMap con:

- `amenity=restaurant`
- `amenity=fast_food`
- `amenity=food_court`

Le fonti e la dicitura `Elaborazione di Nazareno Lecis` sono riportate nei grafici generati.

La serie storica prova a ricostruire 25 anni usando gli snapshot storici OpenStreetMap al 1 gennaio di ogni anno. Gli anni non disponibili nelle fonti ISTAT/Overpass vengono saltati e segnalati durante l'esecuzione. La serie misura la presenza dei POI in OpenStreetMap, non un registro ufficiale delle aperture.

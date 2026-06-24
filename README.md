# Kebabbari

Stima operativa dei kebabbari nelle Marche usando dati aperti e replicabili.

Il progetto usa:

- OpenStreetMap/Overpass per individuare i punti kebab;
- ISTAT Demo POSAS per la popolazione comunale;
- ISTAT confini amministrativi per assegnare ogni punto al comune;
- OpenStreetMap per il denominatore dei punti di ristorazione.

## Uso

Modifica le variabili in `marche_kebab_density.py`, poi esegui:

```powershell
py marche_kebab_density.py
```

Parametro principale per gli output:

```python
TIPO_OUTPUT = "entrambi"  # "csv", "grafici", oppure "entrambi"
```

## Output

Lo script puo' generare:

- CSV con elenco kebabbari;
- CSV con punti OSM di ristorazione;
- distribuzione per comune, provincia e regione;
- grafici SVG con rapporto kebabbari/popolazione;
- grafici SVG con rapporto kebabbari/ristoranti.

## Nota metodologica

`Kebabbaro` non e' una categoria statistica ufficiale. Il conteggio e' quindi una stima operativa basata su punti OpenStreetMap con riferimenti a kebab, kebap, doner o shawarma.

Il rapporto con i ristoranti usa come denominatore i punti OpenStreetMap con:

- `amenity=restaurant`
- `amenity=fast_food`
- `amenity=food_court`

Le fonti e la dicitura `Elaborazione di Nazareno Lecis` sono riportate nei grafici generati.

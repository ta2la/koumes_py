# panel.py

Jeden sloupec okna. Každý panel má stejnou stavbu a liší se jen tím, co si
zapne:

```
[ toolbar   ]  tlačítka (která, říká TOOLBAR té třídy)
[ role bar  ]  jméno role vlevo, přepínač zobrazovačů vpravo
[ info bar  ]  cesta a zobrazovač, každý s kopírovacím tlačítkem
[ obsah     ]  web view, u p1 a p2 přepínatelné s www
```

Třídy na konci souboru (`LeftPanel`, `DirPanel`, `DetailPanel`,
`RightmostPanel`) se od sebe liší pár řádky - seznamem tlačítek a tím, jestli
mají www záložku. Nový panel je tedy nová třída, ne nová kopie stavby.

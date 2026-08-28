# KOUMES - desktopová appka

Qt okno se čtyřmi panely a most mezi nimi a příkazovou vrstvou.

| panel | k čemu je |
|---|---|
| `left` | nadřazený adresář, záložky, log, menu |
| `dir` | hlavní procházení adresářů |
| `p1` | otevřený dokument (nebo web, přepínač `view` / `www`) |
| `p2` | druhý dokument, sem míří `chroma_setfile … --p2` |

## Čím to drží pohromadě

- `main_window.py` - okno, panely a všechno drátování mezi nimi
- `panel_bus.py` - signály "změnil se adresář / vybral se soubor"; panely spolu
  nemluví přímo, potkávají se na sběrnici
- `cmds_chroma.py` - příkazy `chroma_*`, kterými se okno ovládá zvenku
- `viewer_resolver.py` - který `.html` zobrazovač soubor dostane
- `dirview/` - ty zobrazovače

**Panely nikdy nesahají do sebe navzájem.** Klik na tlačítko pošle příkaz, ten
se provede, zaloguje a rozešle - proto umí agent zopakovat úplně všechno, co
umíte myší.

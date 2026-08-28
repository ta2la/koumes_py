# koumes

Prohlížeč souborů a editor, do kterého vidí i váš agent. Člověk klikne v okně,
agent pošle ten samý příkaz po WebSocketu - **jedno rozhraní, dva uživatelé**.

## Jak to spustit

```bash
pip install koumes
koumes                      # otevře aktuální adresář
koumes /cesta/ke/stromu     # sandbox = ten strom
```

WS most poslouchá na `ws://127.0.0.1:12345`. Každý provedený příkaz se
broadcastuje, takže se cizí nástroj může jen připojit a poslat řádek.

## Co kde leží

| adresář | co v něm je |
|---|---|
| `KOUMES/` | desktopová aplikace - okno, panely, zobrazovače |
| `cmd_sys/` | příkazová vrstva a WS most; funguje i bez GUI |
| `config/` | co si appka pamatuje mezi spuštěními |

## Čeho se v kódu držet

- **Modul nesahá do cizího modulu.** `KOUMES/` zná `cmd_sys/`, obráceně to
  neplatí - příkazová vrstva o okně neví a běží i bez něj.
- **Akce se dělá příkazem, ne přímo.** Tlačítko nesáhne do panelu; pošle
  příkaz. Proto je každý pohyb v logu a proto ho umí zopakovat i agent.
- **Komentář říká proč, ne co.** Co dělá řádek, je na řádku vidět.

## Tahle nápověda

Je to obyčejný `.md` soubor vedle toho, co vysvětluje - `KOUMES_PY.help.md`
patří k adresáři `KOUMES_PY`. Tlačítko ❓ vezme vždycky tu nejužší nápovědu,
kterou najde, a když ta chybí, ptá se rodičů. Zkuste to: v `KOUMES/` uvidíte
jinou, u `main_window.py` zase jinou.

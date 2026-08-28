# Zobrazovače

HTML stránky, které kreslí obsah. Appka jim předá cestu k souboru a most
`window.__chroma`; zbytek je na stránce.

| soubor | co kreslí |
|---|---|
| `dirs.html` | výpis adresáře - hlavní pohled prostředního panelu |
| `md-viewer.html` | markdown s čísly fyzických řádků |
| `redline.html` | kreslení do obrázku (rámečky, čáry) |
| `help.html` | tahle nápověda a jí podobné |

## Jak si soubor vybere svůj zobrazovač

Hledá se odspoda nahoru, od adresáře souboru ke kořeni sandboxu: nejdřív
`.t2l/<jméno>.html`, pak `<jméno>.html`. Co se má pro kterou příponu použít,
říká `config.t2l` záznamem `type: viewer_ext`.

Vlastní zobrazovač se tedy přidá tak, že se položí `.html` někam nad soubor,
kterého se týká. Nic se nepřekompilovává.

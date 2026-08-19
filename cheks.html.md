# checks.html - viewer pro checks.t2l

Sidecar viewer pro `checks.t2l` soubory - review nástroj pro C++ → Python port (KOUMES).

## Účel

Každý C++ item (class/method/ctor/data/enum/cmd/macro) má record v `checks.t2l`. Karel prochází record za recordem, ověřuje behavioral ekvivalent v Pythonu, značí stav. Viewer to renderuje gridem s barvou dle statusu.

## Formát recordu

```
type: check
id: <int, 1-based, unique in file>
scope: <C++ item, e.g. CmdArg::isNull, CMD:chroma_setline, MACRO>
kind: class|ctor|method|data|enum|signal|cmd|fn|macro|struct
cpp: <relative path from cvz/ root>:<line> [impl <path>:<line>]
py: <filename>:<line>            # empty pokud dead nebo ještě chybí
what: <krátký popis chování>
status: <empty> | ok | issue | dead
note: <optional; popis divergence u issue, nebo důvod dead>
```

## 5 stavů

| status | ikona | význam |
|--------|-------|--------|
| (empty) | ☐ | nechecknuto |
| `ok` | ✓ | py má behavioral ekvivalent |
| `issue` | ✗ | py chová jinak / diverguje - viz `note:` |
| `dead` | ✓† | C++ item je dead code / not-needed (žádný caller v cvz/, nebo WASM-only, macro, legacy) - intentionally not ported |
| `cpp_specific` | ∅ | C++ item vyžaduje Qt/C++ runtime mechanismus co v Pythonu nedává smysl nebo je pokryto jiným paradigmatem (např. Qt thread affinity assert, Q_ASSERT, Q_PROPERTY, QMetaObject queued invoke) |

`note:` field = tooltip na status box (červená tečkovaná linka pod ikonou).

## Check workflow per item

Kritérium: **C++ → Python behavioral equivalence**. C++ je original, py je port.

### Krok 1: Dead check (pre-condition)

Pro každý item nejdřív ověř jestli je C++ item **volaný** kýmkoli v `cvz/`.

**Grep patterns per kind:**

| kind | grep pattern | poznámka |
|------|--------------|----------|
| class | `\bClassName\b` | typová deklarace vars, member access |
| ctor | `ClassName(` | invocation |
| method | `\.methodName\|->methodName\|ClassName::methodName` | dot/arrow/scope |
| enum val | `\bENUM_VAL\b` | konkrétní hodnota (nikoli enum type) |
| signal/slot | `\bsignalName\b` | connect + emit sites |
| cmd | `"cmd_name"` | registrace + volání (řetězec) |

**Skip dead check pro:**
- `data` (private field) - accessed z vlastní class, vždy má "callera"
- `macro` - preprocessor, těžko trackovatelné

**Bash:**
```bash
grep -rn "<pattern>" CODE_ROOT/ --include="*.cpp" --include="*.h" \
  | grep -v "<own_cpp_file>" | grep -v "<own_h_file>" \
  | head -20
```

Grep scope: **jen `cvz/`**. Ne `unused/`, `secrets/`, `.git/`, apod.

**Výsledek:**
- **0 externích callerů** → `status: dead`, `note: "no callers in cvz/"` (nebo specifičtější důvod)
- **≥1 caller** → pokračuj krokem 2

### Krok 2: Python behavioral compare

Přečti C++ zdroj + Python zdroj (paths z `cpp:` a `py:` field).

**Kritérium: dělá py to samé co c++?** Ne signature match, ne API syntax match. Chování.

**NEpočítá jako issue** (Python-idiomatic):
- Getter metoda vs dataclass field (`arg.name()` vs `arg.name`)
- camelCase vs snake_case rename (`isNull` vs `is_null`, `notifyLineChanged` vs `notify_line_changed`)
- QString vs Python str
- Enum styl (C++ `enum class` vs Python `Enum`)
- Q_INVOKABLE decorator vs `@pyqtSlot`
- Reference-out parameter vs tuple return

**POČÍTÁ jako issue** (funkční divergence):
- Různá logika (jiný algoritmus, edge case chování jinak)
- Chybějící side-effect (C++ notifikuje bus, py ne)
- Odchylka v defaultní hodnotě / návratovém typu
- Chybějící chybová cesta (C++ vrátí null, py raise exception)
- Python přidal něco navíc co C++ nemá (může být OK, ale worth flag)
- Chybí py ekvivalent tam kde má být (portista zapomněl)

**Výsledek:**
- Ekvivalent → `status: ok`
- Divergence → `status: issue` + `note: "<popis>"`

## Batch workflow (per user request "dalsich N")

Po každém batchu N items (default 10):

1. **Edit** - update `status:` (a případně `note:`)
2. **Refresh panelu** - `chroma_reload_detail` na koumes ws://127.0.0.1:54326
   - `panel_reload detail` nefunguje ("no handler for panel detail")
3. **Navigace** - `chroma_setline <id první nevyřízené>` na koumes
   - Scroll je `block: 'center'` - user vidí next task uprostřed s kontextem předchozích i následujících

**Trigger fráze:** `dalsich N`, `prvnich N proved`, `pokracuj`, atd.

## Retro-audit

Pokud se rozšíří kritérium (např. přidán dead check tam, kde dřív nebyl), zpětně projet už udělané `ok` items a rekvalifikovat na `dead` kde třeba. Neplatí pro `data`/`macro` kind (skip).

## Viewer

`checks.html` v `CODE_ROOT/KOUMES_PY/checks.html`. Aktivuje se přes `type: viewer / name: checks` v hlavičce `.t2l` souboru. Viewer_resolver walk-up od souboru najde `checks.html` v `KOUMES_PY/`.

### Interakce

- **Klik na řádek** = highlight modrým outline + publish přes `fs.setSelectedLine(N)` (Karel čte přes `chroma_line`)
- **`chroma_setline N`** = external scroll + highlight (`bus.lineChanged` pro p1, `bus.lineChangedRightmost` pro p2)
- **`chroma_setline N --p2`** = totéž v pravém panelu
- **`?line=N`** query = počáteční selekce (URL param)
- **Tooltip na status ikoně** = `note:` field (červená tečkovaná linka + `cursor: help`)
- **Show cpp checkbox** = toggle zobrazení `cpp:` řádku pod položkou (default hidden)

### Header stats

`Checks: N  ✓ N  ✗ N  ✓† N  ☐ N`

## Related files

- `CODE_ROOT/KOUMES_PY/cmd_sys/checks.t2l` - review port `base2/cmd_sys` + `base2/base2` + `base2/mccp_com`
- `CODE_ROOT/KOUMES_PY/KOUMES/checks.t2l` - review port `APPS/AI_T2LS`

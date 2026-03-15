---
name: printer
description: Manage and interact with network printers using Python and pycups (CUPS). Use this skill whenever the user wants to list available printers on the network, print a file or a web page/URL, or configure printing options (simplex/duplex). If only one printer is available it is selected automatically.
metadata: { "openclaw": {"emoji": "🖨️" } }
---

# Printer Skill

This skill enables  to discover network printers and print files using Python.


---

## Workflow

If you detect more then one printer, ask the user which printer ist the default printer. Remember the response.

### 1. Discover Available Printers

```bash
# JSON output (default) — machine-readable, use this when parsing results
{baseDir}/bin/printer list
{baseDir}/bin/printer list --json

# Text table — human-readable
{baseDir}/bin/printer list --text
{baseDir}/bin/printer list --text --verbose
```

**JSON output format:**

```json
{
  "total": 2,
  "default_printer": "HP_LaserJet",
  "printers": [
    {
      "name": "HP_LaserJet",
      "uri": "ipp://192.168.1.10:631/printers/HP_LaserJet",
      "state": "idle",
      "is_default": true
    },
    {
      "name": "Epson_WF",
      "uri": "ipp://192.168.1.20:631/printers/Epson_WF",
      "state": "stopped",
      "is_default": false
    }
  ]
}
```

With `--verbose`, each printer entry also includes an `"attributes"` object containing all raw CUPS PPD attributes.

### 2. Print a File

```bash
# Single printer available — selected automatically
{baseDir}/bin/printer file --file /path/to/document.pdf

# Use a specific printer
{baseDir}/bin/printer file --file /path/to/document.pdf --printer "HP_LaserJet"

# Print duplex (two-sided)
{baseDir}/bin/printer file --file /path/to/document.pdf --duplex

# Print simplex (one-sided, explicit)
{baseDir}/bin/printer file --file /path/to/document.pdf --simplex

# Combine options
{baseDir}/bin/printer file --file /path/to/document.pdf --printer "HP_LaserJet" --duplex --copies 2
```

### 3. Print a Web Page (URL)

```bash
# Print a web page
{baseDir}/bin/printer page --url https://example.com

# Print in duplex / landscape
{baseDir}/bin/printer page --url https://example.com --duplex --landscape

# Use a specific printer and paper size
{baseDir}/bin/printer page --url https://news.ycombinator.com --printer "HP_LaserJet" --media Letter

# Scale down wide pages to fit on paper (0.8 = 80%)
{baseDir}/bin/printer page --url https://example.com --scale 0.8

# Wait 5 s for animations or lazy-loaded content before rendering
{baseDir}/bin/printer page --url https://example.com --wait 5

# Disable network-idle wait (for live dashboards or streaming pages)
{baseDir}/bin/printer page --url https://dashboard.example.com --no-network-wait

# Combine options
{baseDir}/bin/printer page --url https://example.com --printer "Epson_WF" --duplex --copies 2 --scale 0.9
```

### 4. Print a Text File (with Font Control)

If user ask to print a text file and wnats to control font family and font size.

```bash
# Default font (Courier 10pt)
{baseDir}/bin/printer text --file notes.txt

# Custom font and size
{baseDir}/bin/printer text --file notes.txt --font Helvetica --font-size 11

# Monospace code style, small, landscape for wide output
{baseDir}/bin/printer text --file output.log --font Courier --font-size 8 --landscape

# Loose line spacing and wider margins
{baseDir}/bin/printer text --file readme.txt --line-spacing 1.5 --margin 2.5cm

# Serif font, duplex
{baseDir}/bin/printer text --file report.txt --font Times-Roman --font-size 12 --duplex

# Full control
{baseDir}/bin/printer text --file notes.txt --printer "HP_LaserJet" --font Helvetica-Bold \
    --font-size 10 --line-spacing 1.3 --media Letter --duplex --copies 2
```

**Available built-in fonts** (no external files required):

| Family | Variants |
|---|---|
| Courier | Courier, Courier-Bold, Courier-Oblique, Courier-BoldOblique |
| Helvetica | Helvetica, Helvetica-Bold, Helvetica-Oblique, Helvetica-BoldOblique |
| Times | Times-Roman, Times-Bold, Times-Italic, Times-BoldItalic |

---

### `{baseDir}/bin/printer page` key options

| Option | Default | Description |
|---|---|---|
| `--url` | *(required)* | Web page URL to print |
| `--scale FACTOR` | `1.0` | CSS scale (0.1–2.0); use `0.8` for wide pages |
| `--landscape` | off | Print in landscape orientation |
| `--wait SECONDS` | `0` | Extra delay after load for animations/lazy content |
| `--no-network-wait` | off | Skip network-idle wait (for live/streaming pages) |
| `--viewport-width PX` | `1280` | Chromium browser window width |
| `--media SIZE` | `A4` | Paper size: A4, Letter, Legal, A3, Tabloid, … |

### `{baseDir}/bin/printer text` key options

| Option | Default | Description |
|---|---|---|
| `--file` | *(required)* | Path to the plain text file |
| `--font NAME` | `Courier` | ReportLab built-in font name |
| `--font-size PT` | `10` | Font size in points |
| `--line-spacing FACTOR` | `1.2` | Line height multiplier (1.0 tight … 1.5 loose) |
| `--margin VALUE` | `2cm` | Page margin: `2cm`, `15mm`, `72pt` |
| `--landscape` | off | Print in landscape orientation |
| `--media SIZE` | `A4` | Paper size: A4, Letter, A3, Legal |
| `--encoding ENC` | `utf-8` | Source file character encoding |

---


## Troubleshooting

- **Page renders blank / missing content** → Try `--wait 3`
- **Wide page gets cut off** → Use `--scale 0.8` or `--landscape`
- **Live dashboard never finishes loading** → Use `--no-network-wait`
- **Text font looks wrong** → Check font name spelling; run `printer text --help` for the full list
- **Text file has encoding errors** → Try `--encoding latin-1` or `--encoding utf-8`
- **Printer not listed** → Add it via `http://localhost:631` or `lpadmin`
- **Duplex not working** → Check with `lpoptions -p <printer> -l | grep Duplex`

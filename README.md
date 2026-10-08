# Market Lens (Public Core)

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Database: DuckDB](https://img.shields.io/badge/storage-DuckDB%20%2B%20Parquet-amber.svg)](https://duckdb.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)]()

**Market Lens** is a high-performance financial market analysis and mutual fund intelligence platform designed for Indian (NSE) and US equity markets. Built with enterprise Clean Architecture (Java-to-Python engineering standards), it integrates in-process columnar database storage (DuckDB), real-time news sentiment analysis, and AMFI mutual fund portfolio look-through analytics.

---

## Key Features

1. **In-Process Analytical Database (DuckDB + Parquet)**:
   - High-speed columnar analytics querying multi-year price data and holdings.
   - Partitioned Apache Parquet analytical storage engine with zero vendor lock-in.
2. **AMFI Mutual Fund Look-Through & News Radar**:
   - Ingests official monthly SEBI AMC portfolio disclosures (scheme holdings & stock weights).
   - Correlates real-time breaking news sentiment across fund constituents to detect NAV momentum early.
   - Formulates tactical rotation recommendations (equity funds vs. defensive Stable Money FDs).
3. **Deep Value & Catalyst Opportunity Hunter**:
   - Scans 52-week low valuation discounts and all-time-high drawdowns.
   - Filters out value traps by requiring positive corporate catalysts (mergers, turnaround, capital infusion).
4. **Exchange Calendars & Dual Timezone Support**:
   - Authoritative market hours for NSE (India) and US equities.
   - Dual-timezone formatting: `Local Exchange Time [IST]`.
5. **Technical Indicator Engine**:
   - Vectorized mathematical indicators: ATR, Cumulative VWAP, Exponential Moving Averages (EMA), RSI, and MACD.

---

## Prerequisites & Required Software

* **Python 3.12+**
* **Git** & **GitHub Desktop**
* **Ollama** (Optional: for local AI summarization)

---

## Step-by-Step Installation

### Windows (PowerShell)

```powershell
# 1. Clone repository
git clone https://github.com/Soyabin31/public-market-lens.git
cd public-market-lens

# 2. Create and activate Python 3.12 virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 4. Run tests
pytest
```

### macOS / Linux (Terminal)

```bash
# 1. Clone repository
git clone https://github.com/Soyabin31/public-market-lens.git
cd public-market-lens

# 2. Create and activate Python 3.12 virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 4. Run tests
pytest
```

---

## Architecture & Project Structure

```
public-market-lens/
├── config/                      # YAML configurations (symbols, sources, mood)
├── src/marketlens/
│   ├── calendar/                # Trading exchange calendars & session cutoffs
│   ├── fund/                    # AMFI portfolio look-through & deep value hunter
│   ├── news/                    # RSS news ingestion & market mood sentiment
│   ├── storage/                 # Partitioned Parquet storage engine
│   ├── indicators.py            # Mathematical technical indicators (ATR, VWAP)
│   ├── db.py                    # DuckDB connection & schema initialization
│   └── config.py                # Configuration loader
├── tests/                       # Public test suite
├── pyproject.toml               # Package build specifications
└── requirements.txt             # Dependency declarations
```

---

## License

This project is licensed under the MIT License.

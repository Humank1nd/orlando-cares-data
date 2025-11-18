# orlando-cares-data

Daily scraper for City of Orlando volunteer opportunities for the Orlando Cares Passport.

## Overview

This repository contains a Python scraper that automatically fetches volunteer opportunities from [volunteer.orlando.gov](https://volunteer.orlando.gov/custom/501/opp_search) and saves them to a JSON file. The scraper runs daily via GitHub Actions and automatically commits the updated data to the repository.

## Setup

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Installation

1. **Create a virtual environment** (recommended):

```bash
python3 -m venv venv
```

2. **Activate the virtual environment**:

   - On Windows:
   ```bash
   venv\Scripts\activate
   ```

   - On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Verify Python version**:

```bash
python --version
```

Should show Python 3.11 or higher.

## Usage

### Running the Scraper Locally

To run the scraper manually:

```bash
python scraper.py
```

The scraper will:
- Fetch volunteer opportunities from the target URL
- Parse and extract opportunity data (title, description, link, date, location, etc.)
- Save results to `orlando_cares_opportunities.json`
- Print the number of opportunities scraped

### Output Format

The scraper generates `orlando_cares_opportunities.json` with the following structure:

```json
{
  "scraped_at": "2024-01-01T00:00:00",
  "source_url": "https://volunteer.orlando.gov/custom/501/opp_search",
  "total_opportunities": 42,
  "opportunities": [
    {
      "title": "Opportunity Title",
      "link": "https://...",
      "description": "...",
      "date": "...",
      "location": "..."
    }
  ]
}
```

## GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/scrape.yml`) that:

- Runs automatically every day at midnight UTC
- Can be manually triggered from the Actions tab
- Installs dependencies, runs the scraper, and commits the updated JSON file

### Enabling GitHub Actions

1. Go to your repository settings on GitHub
2. Navigate to "Actions" → "General"
3. Ensure "Allow all actions and reusable workflows" is selected
4. The workflow will run automatically on the schedule

### Manual Trigger

To manually trigger the workflow:

1. Go to the "Actions" tab in your GitHub repository
2. Select "Daily Scraper" from the workflow list
3. Click "Run workflow" and select the branch

## Customization

If the website structure changes, you may need to update the selectors in `scraper.py`. The main functions to modify are:

- `find_opportunities()`: Adjust selectors to find opportunity containers
- `extract_opportunity_data()`: Update field extraction logic

## Troubleshooting

- **No opportunities found**: The HTML structure may have changed. Inspect the website and update the selectors in `scraper.py`.
- **GitHub Actions fails**: Ensure Actions are enabled in repository settings and the workflow file is valid YAML.
- **Permission errors**: The workflow needs `contents: write` permission to commit changes.

## License

See LICENSE file for details.

# SmartHam

Canadian amateur radio exam study platform with practice quizzes, timed mock exams, Ollama tutoring, and gamified awards. Styled after [SmartInbox](https://github.com/datagod/SmartInbox).

**Created with Grok Build**

## Features

- Ingests ISED Basic and Advanced question bank PDFs from a local folder (Samba share)
- Practice quiz with streak tracking and section filters
- Timed mock exams (Basic: 100 questions / 70% pass, Advanced: 50 questions / 70% pass)
- Ollama explanations when you answer incorrectly
- Study library with on-demand Ollama summaries of reference PDFs
- Ham-themed awards (First Contact, Copy Perfect, Exam Ready, and more)

## Requirements

- Python 3.10+
- ISED question bank PDFs (not included — configure your own path)
- [Ollama](https://ollama.com/) for explanations and study summaries (optional but recommended)

## Quick start

```bash
cd smartham
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp config.example.yaml config.yaml
# Edit pdf_source_path to your hamradio folder

smartham ingest
smartham serve
```

Open http://127.0.0.1:8091

## Configuration

`config.yaml`:

```yaml
host: 127.0.0.1
port: 8091
data_dir: data
pdf_source_path: /home/bill/TRANSFER/hamradio

ollama:
  base_url: http://127.0.0.1:11434
  model: llama3.2
  timeout: 120
```

Expected PDF filenames:

- `amateur_basic_questions_en.pdf`
- `amateur_advanced_questions_en.pdf`
- `Reference Material for Amateur Radio Training Basic EN 2025.pdf`
- `Reference Material for Amateur Radio Exam Basic EN 2025.pdf`
- `Q_Codes_Decoded_Podcast_Book.pdf`

## Legal

Question banks are © Innovation, Science and Economic Development Canada (ISED). SmartHam is an unofficial study aid. Obtain official materials from [ISED](https://ised-isde.canada.ca/site/amateur-radio-operator-certificate-services/en) or [Radio Amateurs of Canada](https://www.rac.ca/).
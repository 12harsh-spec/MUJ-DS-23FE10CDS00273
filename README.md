# College Notice → Student Action Extractor

Turn a college circular, email, or forwarded notice into structured action items,
deadlines, event dates and times, priorities, required documents, and a checklist.
The Streamlit dashboard accepts pasted text or a `.txt` upload.

## How it works
1. `prompts/prompts.yaml` contains the system task, JSON schema guidance, user template,
   and repair prompt. The same prompt is used in Gemini Mode.
2. `src/llm_client.py` sends notices to Gemini through Google's official `google-genai`
   SDK. `GEMINI_API_KEY` is read server-side from the environment or `.env`.
3. `src/extractor.py` parses the JSON response and validates it with Pydantic in
   `src/schema.py`. Invalid JSON/schema responses are sent through the prompt repair loop.
4. `src/exporters.py` produces Markdown checklists and calendar `.ics` files.
5. If the key is missing, or a Gemini request fails, the app can use the deterministic
   local extractor in `src/demo_extractor.py`. Demo Mode is not an LLM and is labeled as such.

## Setup
Python 3.10+ is recommended.

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Gemini API key
1. Create a key in [Google AI Studio](https://aistudio.google.com/apikey).
2. Copy `.env.example` to `.env` and set `GEMINI_API_KEY` to your key.
3. Keep `.env` private. It is ignored by Git; never paste the key into source code or the README.

PowerShell:
```powershell
Copy-Item .env.example .env
```

macOS/Linux:
```bash
cp .env.example .env
```

The key is only read by Python on the server. It is never sent to browser code.

## Run
```bash
python -m streamlit run app.py
```

Run the command-line extractor on bundled samples:
```bash
python -m src.main samples/
python -m src.main samples/exam_form.txt --today 2026-09-29
```

## Modes
**Gemini Mode** is selected when `GEMINI_API_KEY` is configured. The app sends the
notice and YAML prompt to the configured Gemini model, requests JSON output, validates
the response, and displays **AI Mode • Gemini**.

**Demo Mode** is selected when the key is absent. It uses deterministic Python rules
to find likely actions, dates, priorities, fees, and documents; it does not call or
pretend to be an LLM. If Gemini is configured but a request fails, the app shows a
friendly message and uses the same local fallback for that notice.

## Configuration
Set the provider and model in `config.yaml`:
```yaml
llm:
  provider: gemini
  model: gemini-3.8-flash
```

The prompt remains in `prompts/prompts.yaml`; no prompt is hardcoded in the API client.

## Example
For `samples/exam_form.txt`, using 1 October 2026 as the reference date, expected
actions include:
- Fill the examination form on the ERP portal by Friday, 9 October 2026.
- Pay the Rs 1500 examination fee online.
- Submit a condonation application and medical certificate to the HOD office if
   attendance is below 75%.

## Project structure
```text
app.py                    Streamlit dashboard and provider selection
config.yaml               Gemini model and generation settings
prompts/prompts.yaml      Shared Gemini extraction and repair prompts
src/llm_client.py         Official Google Gemini SDK client
src/demo_extractor.py     Deterministic no-key fallback
src/schema.py             Validated action/result models
src/extractor.py          JSON parsing, validation, and repair flow
src/exporters.py          Markdown and calendar exports
tests/                    Provider, fallback, parser, UI, and export tests
```

## Testing
```bash
python -m pytest
```
All provider calls are mocked in tests; the suite does not make real Gemini requests
and does not require an API key.

## Limitations
Only pasted text and plain-text `.txt` uploads are supported; paste PDF text first.
Demo Mode uses deterministic rules and may miss nuanced meaning. Gemini Mode can also
misinterpret ambiguous notices, so review extracted actions before relying on them.


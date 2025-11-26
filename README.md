

Stanford CS PhD undergrad data (2025 cohort) collected via GPT‑5 with the web search tool. The repo holds the raw name list, intermediate model outputs, a merged/cleaned file, and a count table of undergraduate institutions.

- **Prereqs:** Python 3.10+, `pip install openai pandas` (pandas is only needed for the MIT/CMU helper scripts), and `OPENAI_API_KEY` set. Web search access must be enabled on the API key.
- **Key files:** `stanford_intermediate_files/stanford_raw_2025.txt` (raw names), `stanford_raw_2025_processed_merged.txt` (final Name | School list), `stanford_raw_2025_processed_merged_counts.txt` (school counts).

Stanford workflow
- Run the initial lookup (names only, one per line):  
  `python gpt5_web_search.py stanford_intermediate_files/stanford_raw_2025.txt`
- Retry unknown rows from a processed file (uses high reasoning by default):  
  `python gpt5_web_search.py stanford_intermediate_files/stanford_raw_2025_processed.txt --retry-unknowns`
- Merge one or more retry/manual-fix files back into the base processed file:  
  `python gpt5_web_search.py stanford_raw_2025_processed.txt --merge-with stanford_intermediate_files/stanford_raw_2025_processed_unknown_retry.txt stanford_intermediate_files/stanford_raw_2025_processed_unknown_retry_unknown_retry_manual_fix.txt`
- Produce the school-count table (alias-aware):  
  `python aggregate_counts.py stanford_raw_2025_processed_merged.txt`

Notes
- `gpt5_web_search.py` writes outputs next to the input file by default (suffix `_processed`, `_unknown_retry`, `_merged`); use `-o` to override. Adjust batch size with `-n` if rate limits hit.
- The alias map in `aggregate_counts.py` collapses common spelling variants/abbreviations before counting.
- `other_universities/main_mit.py` and `other_universities/main_cmu.py` are clipboard-based scripts for quick counts of MIT/CMU lists formatted as `Name | Undergraduate Institution`.

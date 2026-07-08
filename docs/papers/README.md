# Papers

Background reading referenced by the codebase.

## Fuzzing

- **`fuzzing-art-science-engineering-survey.pdf`** —
  V. J. M. Manès, H. Han, C. Han, S. K. Cha, M. Egele, E. J. Schwartz,
  M. Woo, *"The Art, Science, and Engineering of Fuzzing: A Survey"*
  (arXiv:1812.00140). A taxonomy of fuzzing, including the coverage-guided
  (AFL/libFuzzer) and property/generational approaches used by
  [`backend/fuzz`](../../backend/fuzz), which fuzzes the untrusted-input
  parsers with Hypothesis (property-based) and Atheris (coverage-guided).

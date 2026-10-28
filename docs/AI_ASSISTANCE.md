# AI assistance and contribution boundaries

## Scope of this disclosure

The October 2026 CinematicDX update was developed with assistance from OpenAI Codex. Git commits use the repository owner's configured identity; that identity alone should not be read as a claim that every line or report sentence was written manually. The `codex/` branch prefix records the development workflow. The default mainline remains `master`.

## Researcher-supplied material

The researcher supplied the PhD objectives, conceptual distinctions, corpus inventory and permitted materials, task priorities, resource limits, interpretation constraints and publication instructions. The existing *Shang Gan Ling* shot-boundary and narrative-event annotations were made independently by the researcher. Their original values and stated temporal uncertainty were retained. Codex did not replace those annotations with inferred labels.

## Codex-assisted work

Assistance covered code inspection and implementation, metadata storage/configuration, GUI and interaction design, tests, build tooling, bounded computational experiments, numerical checks, technical audits, methodological notes, screenshots and presentation assembly. The reports identify the actual input versions, parameters, available checks and limitations where evidence is present.

Some source-identity and image-failure observations were made by the assistant. They are recorded as assistant observations, not as additional independent human annotation or archival verification. Numerical reproducibility is a separate claim from measurement validity or film-historical interpretation.

The 28 October results presentation reuses saved measurements, plots and actual GUI screenshots. It adds an explanation of their generation and synthesises existing findings. It does not represent a new film extraction, a new independent validation sample or coauthor approval of the interpretations.

## Research and software boundaries

- The desktop application manages metadata and opens local evidence folders. Its optional worker is not an implemented GUI-driven CV pipeline.
- Automatic cut/transition outputs remain predictions or candidates with the documented validation scope. Independent narrative reference data remain a separate layer.
- Tests of storage, timestamps and arithmetic do not by themselves establish film-theoretical validity. The limited hard-cut reference does not establish corpus-wide accuracy, and the tested gradual detector does not reliably delimit complete transitions.
- Observed gray-level and candidate-rate differences do not establish narrative causation, a stable institutional style or a socio-political explanation. Historical interpretation and authorship decisions remain research judgements.
- Source videos, original annotation/inventory files, credentials, local catalogs and model/runtime caches are not included in this publication. Selected screenshots and aggregate results appear in the repository documentation and presentation.

## Collaboration and publication

The researcher authorised the work and this mainline publication. This is not evidence that other coauthors have independently reviewed or endorsed the code, measurements or interpretations. The README and update record provide the disclosure for collaborators; no direct individual notification is claimed.

Future changes should keep implementation, empirical output, human reference data and interpretation traceable. Substantial updates should describe their scope and Codex involvement in an English commit or merge message and the relevant update record. Development branches may use `codex/`; mainline publication should follow the researcher's current instructions and preserve existing history. Do not infer authority to contact individual collaborators, publish new research claims or merge future changes from the branch name.

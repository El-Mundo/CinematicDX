## Methodological Vision: LoD-Aware Corpus Design for Computational Film Analysis

This project explores a **Level-of-Detail (LoD) aware corpus architecture** for moving-image research. The initial motivation comes from a methodological problem in digital film studies: how can a researcher move between distant reading and close reading without treating them as two separate or opposed modes of analysis?

In traditional film studies, close reading usually works through careful attention to individual films, scenes, shots, and frames. Distant reading, by contrast, works through abstraction, aggregation, and comparison across larger corpora. However, moving-image data complicates this distinction. A film corpus is not only a collection of titles or metadata; it is also a large-scale visual, temporal, and computational object. A corpus of hundreds of films may contain millions of frames, thousands of shots, and multiple layers of metadata, production history, formal features, and interpretive context.

This project treats **LoD not merely as a technical optimisation, but as a methodological and cultural concept**. LoD provides a way to define, store, visualise, and analyse film data at different scales:

Corpus → Film → [Scene] → Shot → Frame

The optional Scene level is included because it often functions as an interpretive bridge between machine-readable units such as shots and frames, and humanistic units such as narrative sequence, dramatic situation, or historical argument.

The central idea is that the space between distant reading and close reading should not be understood as a binary opposition. Instead, it can be modelled as a continuous analytical space in which different levels of detail are selected according to the research question, available evidence, and computational cost.
Corpus as Database, Not Just Metadata

A simplified conceptual structure is:
Corpus
  └── Film
        ├── Metadata
        ├── Optional media reference
        ├── Concepts / tags / historical categories
        ├── Segmentation data
        │     ├── Scene
        │     ├── Shot
        │     └── Frame / sampled frame
        ├── Feature layers
        │     ├── string
        │     ├── integer
        │     ├── float
        │     ├── boolean
        │     ├── vector
        │     └── other extensible data types
        └── Provenance / analysis history

The database is intended to support not only filmographic metadata, but also computationally generated features, manually curated annotations, imported tabular data, and future machine-learning outputs.

JavaFX as a Reading and Visualisation Interface

The main GUI is designed in JavaFX. Its primary role is not to perform heavy computation directly, but to provide a visual and interactive interface for reading the corpus.

### Why Distance and LoD Matter for Humanistic Evidence

A further theoretical motivation for this project concerns the nature of humanistic data itself.

Humanistic data is never simply neutral or objective material. It is usually produced, selected, preserved, classified, translated, and interpreted through particular historical, institutional, political, and cultural positions. A film corpus, an archive catalogue, a museum collection, a list of production credits, or a set of genre labels is always shaped by decisions about what counts, what is visible, what is excluded, and what is worth preserving.

This creates a familiar tension in the humanities: the tension between the canonical and the vernacular, the central and the local, the official and the marginal. One might argue that local histories, vernacular archives, and culturally specific categories deserve more attention precisely because they resist the simplifying force of grand narratives. However, this does not mean that the most local or most specific object is automatically the most meaningful object of study.

If classification depends only on qualitative interpretation, the possible subdivision of locality is almost endless. A “local” history may refer to a national cinema, a regional film industry, a city archive, a county museum, a community organisation, a family collection, or even the private collection of a single individual. Conversely, a supposedly “central” or “canonical” history may refer to a national archive, a state-sponsored filmography, a university collection, a global museum, or a large institutional database. Each of these positions can be challenged by a case that is either more central or more local.

In other words, the opposition between centre and locality is not a stable binary. It is a scale.

This matters because research projects are also shaped by imagined audiences. A digital humanities project may be designed for a local community, for specialists in a specific field, for comparative scholars, or for broader methodological debates. Yet these audiences do not always remain separate. A project that begins as a local or vernacular archive may later contribute to a wider discussion about digital method, corpus design, visualisation, or cultural analytics. Conversely, a large-scale methodological project may need to return to highly local evidence in order to remain historically responsible.

Binary language such as “canonical versus vernacular” or “distant versus close” can therefore obscure the more complex space between these positions. The relationship between centre and locality, like the relationship between distant reading and close reading, is better understood as a continuous and negotiable field of scale.

This is where LoD becomes methodologically useful.

LoD does not claim that all scales are equivalent, nor does it dissolve historical specificity into abstract data. Instead, it provides a way to make scale explicit. It allows a researcher to ask:

- At what level is this object being studied?
- Is the relevant unit a corpus, a film, a scene, a shot, a frame, a person, a production company, a local archive, or a historical concept?
- What is gained by moving outward toward aggregation?
- What is lost when detail is reduced?
- What becomes visible only when one moves inward toward local evidence?
- Can a local case contribute to a more general methodological problem?
- Can a large-scale pattern be returned to inspectable evidence?

In this sense, LoD is not only a computational strategy. It is a way of making the politics and epistemology of scale visible.
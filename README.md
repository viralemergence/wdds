# wdds
This repo is a storage location for Wild Disease Data Standard files.

## Abstract
Rapid and comprehensive data sharing is vital to the transparency and actionability of wildlife infectious disease surveillance and research.
Unfortunately, most best practices for publicly sharing these data are focused on pathogen determination and genetic sequence data. 
Other facets of wildlife disease data – particularly negative results – are often withheld or, at best, summarized in a descriptive table with limited metadata. 
Here, we provide a minimum data and metadata reporting standard for wildlife disease studies. 
Our data standard identifies a set of 41 data fields (9 required) and 24 metadata (7 required) fields sufficient to standardize and document a dataset consisting of records disaggregated to the finest possible spatial, temporal, and taxonomic scale. 

## Data Validation Package

For convenience, we have developed the [wddsWizard](https://viralemergence.github.io/wddsWizard) R package for data validation. 

The wddsWizard package contains [searchable documentation for terms](https://viralemergence.github.io/wddsWizard/articles/schema_overview.html#terms). 

Data can also be validated against the JSON schema using a validation engine (e.g. [AJV](https://ajv.js.org/guide/getting-started.html)).

## Versioning

1) All versions of WDDS will include a version number in their title (e.g. v1.0.0). 
    - Changes including updating required fields, changing field names, adding or removing value restrictions, or other breaking changes will result in a major release bump (1.0.0 -> 2.0.0)
    - Non-breaking changes that impact validation - refining regex patterns, correcting or refining enum values, etc - will result in a minor release bumb (1.0.0 -> 1.1.0)
    - Non-breaking changes that do not impact validation - updating descriptions, adding examples, etc - will result in a patch release bumb (1.0.0 -> 1.0.1)
2) When a new version of the schema is published, a new github release will be created as well as a new version of the schema on Zenodo
3) `wddsWizard` and other validation libraries we may create will use the most recent version of the data standard by default.





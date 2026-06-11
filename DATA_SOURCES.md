# Data Sources, Licenses & Attribution

UnaBetting's **code** is MIT-licensed. The **data** it consumes is NOT ours and
carries its own licenses. If you use this project, you inherit these obligations.

## Jeff Sackmann / Tennis Abstract (match results, rankings, point-by-point)

> Tennis databases, files, and algorithms by [Jeff Sackmann / Tennis Abstract](http://www.tennisabstract.com/)
> are licensed under a [Creative Commons Attribution-NonCommercial-ShareAlike 4.0
> International License](https://creativecommons.org/licenses/by-nc-sa/4.0/).

- Repositories: [tennis_atp](https://github.com/JeffSackmann/tennis_atp),
  [tennis_wta](https://github.com/JeffSackmann/tennis_wta),
  [tennis_pointbypoint](https://github.com/JeffSackmann/tennis_pointbypoint)
- **Attribution is required. Non-commercial use only. Share-alike.**
- ⚠️ Consequence for this project: any use of UnaBetting involving Sackmann-derived
  data (features, trained models, predictions) **must remain non-commercial**.
  Datasets are NOT redistributed in this repo — the pipeline downloads them from
  the source so the license stays with the origin.

## tennis-data.co.uk (historical betting odds)

- Source: [tennis-data.co.uk](http://www.tennis-data.co.uk/) — free historical
  results & fixed odds for personal / non-commercial use; attribution appreciated.
- Not redistributed here; downloaded by the pipeline.

## The Odds API (live odds)

- Source: [the-odds-api.com](https://the-odds-api.com/) — commercial API used under
  its own [Terms of Use](https://the-odds-api.com/liveapi/guides/v4/#terms-of-use);
  requires your own API key. Odds data is **not** stored in this repository
  (`data/live/` is gitignored).

## TML-Database

- Source: [Tennis-Match-Loader database](https://github.com/Tennismylife/TML-Database)
  — community match database, used for recent-season coverage.

## Summary

| Source | License | Redistributed here? | Commercial use |
|---|---|---|---|
| Jeff Sackmann | CC BY-NC-SA 4.0 | No | **Forbidden** |
| tennis-data.co.uk | site terms (personal use) | No | No |
| The Odds API | commercial ToS, own key | No | per their ToS |
| TML-Database | repo terms | No | check upstream |

**Bottom line: UnaBetting is and must remain a non-commercial research project
as long as it builds on these sources.**

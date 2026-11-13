# Working together on EuropeTravel

## Branches

- `main` always runs. Don't commit to it directly once the team has joined.
- One branch per piece of work: `feature/<short-name>`, `fix/<short-name>`, `data/<short-name>`, `docs/<short-name>`.

## Workflow

1. `git checkout main && git pull`
2. `git checkout -b feature/activity-filter`
3. Commit in small steps.
4. `git push -u origin feature/activity-filter`
5. Open a pull request on GitHub.
6. One teammate reviews and approves.
7. Merge into `main`, then delete the branch.

## Commit messages

```
<type>: <what changed>
```

Types: `feat`, `fix`, `data`, `docs`, `test`, `refactor`, `style`.

```
feat: add activity filter to the panel
data: rebuild climate for all regions
fix: keep the drawer open when the threshold changes
test: cover regions without climate data
```

## Pull requests

- Use the same title format as commits.
- Say what changed and how to test it.
- Keep each pull request to one feature.
- Don't merge your own pull request.
- Run `pytest` before you push.

## Who owns what

| Area | Main files |
|---|---|
| Backend and API | `app.py`, `store.py` |
| Matching and tests | `matcher.py`, `tests/` |
| Map and interface | `static/js/`, `static/css/`, `templates/` |
| Data and docs | `scripts/`, `data/`, `README.md`, `STATUS.md` |

`data/regions.json`, `data/cities.json` and `data/places.json` are generated.
Change `data/curated/*.json` or the scripts, then run
`python -m scripts.build_data merge`. Editing the generated files by hand
causes merge conflicts and the next build overwrites the edit.

## Before your first commit

Git uses your name and email to credit your commits. The email must be one
that is verified on your GitHub account, or the commits won't count as yours.

```bash
git config --global user.name "Your Name"
git config --global user.email "the-email-on-your-github-account@example.com"
```

## Everyday commands

```bash
git status
git add <files>
git commit -m "feat: add region detail endpoint"
git pull --rebase origin main   # keep your branch up to date
git push
```

If a merge conflict appears, open the file, resolve the part between the
`<<<<<<<` and `>>>>>>>` markers with whoever wrote the other side, then
`git add` the file and continue.

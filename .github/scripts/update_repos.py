#!/usr/bin/env python3
"""Regenerate the AUTO-REPOS section of the profile README from the owner's repos.

Runs in GitHub Actions. Lists every public repo, drops the profile repo and the
two hand-featured heroes, and renders arcade-style cards between the markers.
New repos you create show up here on the next scheduled run — no manual work.
"""
import json, os, re, sys, urllib.request

OWNER = os.environ.get("OWNER", "Yashwanth-pilli")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = "README.md"
START, END = "<!-- AUTO-REPOS:START -->", "<!-- AUTO-REPOS:END -->"

# already featured by hand above the auto section (skip to avoid duplicates)
HEROES = {OWNER.lower(), "illip-ai", "quantumshield-biodefense-os"}
# accent colors cycled across cards for variety
COLORS = ["8b7bff", "00e676", "6d5efc", "ff9100", "00b0ff", "ff4081", "c9d1d9"]


def api(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-updater",
        **({"Authorization": f"token {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def all_repos():
    out, page = [], 1
    while True:
        batch = api(f"https://api.github.com/users/{OWNER}/repos"
                    f"?per_page=100&sort=pushed&page={page}")
        if not batch:
            break
        out += batch
        if len(batch) < 100:
            break
        page += 1
    return out


def card(repo, color):
    name = repo["name"]
    desc = (repo.get("description") or "").strip() or "_no description yet_"
    fork = " · 🍴 fork" if repo.get("fork") else ""
    lc = (f'https://img.shields.io/github/last-commit/{OWNER}/{name}'
          f'?style=flat-square&color={color}&labelColor=0d1117')
    tl = (f'https://img.shields.io/github/languages/top/{OWNER}/{name}'
          f'?style=flat-square&color={color}&labelColor=0d1117')
    star = (f'https://img.shields.io/github/stars/{OWNER}/{name}'
            f'?style=flat-square&color={color}&labelColor=0d1117&logo=github')
    btn = (f'https://img.shields.io/badge/%E2%96%B6%20ENTER-{color}'
           f'?style=for-the-badge&logo=github&logoColor=white')
    url = repo["html_url"]
    return (
        f'\n### 🌍 &nbsp;{name}{fork}\n\n'
        f'{desc}\n\n'
        f'<img src="{star}" alt="stars"/> '
        f'<img src="{tl}" alt="lang"/> '
        f'<img src="{lc}" alt="commit"/>\n\n'
        f'<a href="{url}"><img src="{btn}" alt="enter"/></a>\n'
    )


def build(repos):
    repos = [r for r in repos if r["name"].lower() not in HEROES]
    if not repos:
        return "<!-- no extra repos yet -->"
    rows = []
    for i in range(0, len(repos), 2):
        pair = repos[i:i + 2]
        cells = ""
        for j, repo in enumerate(pair):
            color = COLORS[(i + j) % len(COLORS)]
            cells += (f'<td width="50%" valign="top" align="center">\n'
                      f'{card(repo, color)}\n</td>\n')
        if len(pair) == 1:  # pad so single card stays half-width
            cells += '<td width="50%"></td>\n'
        rows.append(f'<tr>\n{cells}</tr>')
    table = '<table width="100%">\n' + "\n".join(rows) + '\n</table>'
    return f'<h3 align="center">🗺️ MORE WORLDS</h3>\n\n{table}'


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    if START not in text or END not in text:
        print("markers missing; nothing to do")
        return
    block = build(all_repos())
    new = re.sub(re.escape(START) + r".*?" + re.escape(END),
                 f"{START}\n{block}\n{END}", text, flags=re.S)
    if new == text:
        print("no change")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(new)
    print("README updated")


if __name__ == "__main__":
    main()

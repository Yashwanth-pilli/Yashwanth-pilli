#!/usr/bin/env python3
"""Self-refresh the profile README from the owner's GitHub data.

Runs in GitHub Actions. Regenerates three marked sections automatically, so the
profile keeps itself current — new repos, latest activity, and live totals — with
zero manual editing:
  * AUTO-REPOS     — every public repo as a card (originals ranked, forks grouped)
  * AUTO-ACTIVITY  — the latest public events (pushes, new repos, stars)
  * AUTO-STATS     — totals: public repos, total stars, top languages
Live shields (stars/last-commit/followers) and the snake update on their own too.
"""
import datetime as _dt
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


def card(repo, color, icon):
    name = repo["name"]
    desc = (repo.get("description") or "").strip() or "_no description yet_"
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
        f'\n### {icon} &nbsp;{name}\n\n'
        f'{desc}\n\n'
        f'<img src="{star}" alt="stars"/> '
        f'<img src="{tl}" alt="lang"/> '
        f'<img src="{lc}" alt="commit"/>\n\n'
        f'<a href="{url}"><img src="{btn}" alt="enter"/></a>\n'
    )


def order(repos):
    """Deterministic, meaningful order: most stars first, then most recently
    updated, then name. Same input always yields the same layout."""
    return sorted(
        repos,
        key=lambda r: (
            -(r.get("stargazers_count") or 0),
            # pushed_at desc: invert by negating the char codes via reverse cmp
            tuple(-ord(c) for c in (r.get("pushed_at") or "")),
            r["name"].lower(),
        ),
    )


def grid(repos, icon):
    rows = []
    for i in range(0, len(repos), 2):
        pair = repos[i:i + 2]
        cells = ""
        for j, repo in enumerate(pair):
            color = COLORS[(i + j) % len(COLORS)]
            cells += (f'<td width="50%" valign="top" align="center">\n'
                      f'{card(repo, color, icon)}\n</td>\n')
        if len(pair) == 1:  # pad so a lone card stays half-width, never full
            cells += '<td width="50%"></td>\n'
        rows.append(f'<tr>\n{cells}</tr>')
    return '<table width="100%">\n' + "\n".join(rows) + '\n</table>'


def build(repos):
    repos = [r for r in repos if r["name"].lower() not in HEROES]
    originals = order([r for r in repos if not r.get("fork")])
    forks = order([r for r in repos if r.get("fork")])
    if not originals and not forks:
        return "<!-- no extra repos yet -->"
    parts = []
    if originals:
        parts.append('<h3 align="center">🚀 MORE PROJECTS</h3>\n\n'
                     + grid(originals, "🌍"))
    if forks:
        parts.append('<h3 align="center">🍴 FORKS &amp; EXPERIMENTS</h3>\n\n'
                     + grid(forks, "🔧"))
    return "\n\n<br/>\n\n".join(parts)


def _ago(iso):
    if not iso:
        return ""
    try:
        t = _dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return ""
    s = (_dt.datetime.utcnow() - t).total_seconds()
    for n, u in ((86400, "d"), (3600, "h"), (60, "m")):
        if s >= n:
            return f"{int(s // n)}{u} ago"
    return "just now"


def activity_block():
    """Latest public events as a tidy list."""
    try:
        events = api(f"https://api.github.com/users/{OWNER}/events/public?per_page=30")
    except Exception:
        return "<!-- activity unavailable -->"
    icons = {"PushEvent": "🔨", "CreateEvent": "✨", "WatchEvent": "⭐",
             "ForkEvent": "🍴", "PullRequestEvent": "🔀", "IssuesEvent": "📌",
             "ReleaseEvent": "🚀", "PublicEvent": "📢"}
    lines, seen = [], set()
    for e in events:
        t = e.get("type"); repo = e.get("repo", {}).get("name", "")
        when = _ago(e.get("created_at"))
        if t == "PushEvent":
            pl = e.get("payload", {})
            n = pl.get("size") or len(pl.get("commits", []) or [])
            txt = (f'pushed {n} commit{"s" if n != 1 else ""} to `{repo}`'
                   if n else f'pushed to `{repo}`')
        elif t == "CreateEvent":
            rt = e.get("payload", {}).get("ref_type", "")
            txt = f'created {rt} in `{repo}`'
        elif t == "WatchEvent":
            txt = f'starred `{repo}`'
        elif t == "ForkEvent":
            txt = f'forked `{repo}`'
        elif t == "PullRequestEvent":
            txt = f'{e.get("payload", {}).get("action", "updated")} a PR in `{repo}`'
        elif t == "ReleaseEvent":
            txt = f'released in `{repo}`'
        else:
            continue
        key = (t, repo, txt)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f'- {icons.get(t, "•")} {txt} &nbsp;·&nbsp; _{when}_')
        if len(lines) >= 6:
            break
    if not lines:
        return "<!-- no recent public activity -->"
    return "\n".join(lines)


def stats_block(repos):
    pub = [r for r in repos if not r.get("private")]
    total_stars = sum(r.get("stargazers_count") or 0 for r in pub)
    langs = {}
    for r in pub:
        L = r.get("language")
        if L:
            langs[L] = langs.get(L, 0) + 1
    top = sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    def badge(label, value, color):
        label = str(label).replace("-", "--").replace("_", "__").replace(" ", "%20")
        value = str(value).replace("-", "--").replace("_", "__").replace(" ", "%20")
        return (f'![{label}](https://img.shields.io/badge/{label}-{value}-{color}'
                f'?style=for-the-badge&labelColor=0d1117)')
    out = ['<div align="center">', "",
           badge("Public%20Repos", len(pub), "8b7bff") + " " +
           badge("Total%20Stars", f"%E2%98%85%20{total_stars}", "00e676"), ""]
    if top:
        colors = ["8b7bff", "00e676", "6d5efc", "ff9100", "00b0ff", "ff4081"]
        chips = " ".join(badge(name, f"{cnt}%20repo{'s' if cnt != 1 else ''}",
                               colors[i % len(colors)])
                         for i, (name, cnt) in enumerate(top))
        out += ["**Top languages across my repos**", "", chips, ""]
    out.append("</div>")
    return "\n".join(out)


def replace_section(text, start, end, block):
    if start not in text or end not in text:
        return text, False
    new = re.sub(re.escape(start) + r".*?" + re.escape(end),
                 f"{start}\n{block}\n{end}", text, flags=re.S)
    return new, (new != text)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    repos = all_repos()
    stamp = _dt.datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    changed = False
    for start, end, block in (
        (START, END, build(repos)),
        ("<!-- AUTO-ACTIVITY:START -->", "<!-- AUTO-ACTIVITY:END -->",
         activity_block() + f"\n\n<sub>⟳ auto-refreshed {stamp}</sub>"),
        ("<!-- AUTO-STATS:START -->", "<!-- AUTO-STATS:END -->",
         stats_block(repos)),
    ):
        text, did = replace_section(text, start, end, block)
        changed = changed or did

    if not changed:
        print("no change")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print("README refreshed")


if __name__ == "__main__":
    main()

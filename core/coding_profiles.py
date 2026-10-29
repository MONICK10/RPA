# F1 — coding profiles (LeetCode / HackerRank) as verified evidence.
# Pure mapping + merge logic here; fetch/cache is best-effort and never blocks
# the app (see FEATURE_ADDENDUM.md F1.4 — the offline problem).

import datetime

from core.storage import load_coding_cache, save_coding_cache

FETCH_TIMEOUT_SECONDS = 5.0


# ---------------------------------------------------------------------------
# F1.5 — platform stats -> levels 1-10 for DSA, COD, APTI
# ---------------------------------------------------------------------------

def leetcode_to_levels(stats: dict) -> dict[str, dict]:
    """Returns {code: {"level": int, "reason": str}} for DSA, COD, APTI."""
    total = stats.get("total_solved") or 0
    hard = stats.get("hard") or 0
    rating = stats.get("contest_rating") or 0

    # DSA — volume, then adjusted for difficulty and contest performance.
    if total < 50:
        dsa = 3
    elif total < 150:
        dsa = 5
    elif total < 300:
        dsa = 6
    elif total < 500:
        dsa = 7
    else:
        dsa = 8
    dsa_bits = [f"{total} solved"]

    hard_pct = (hard / total * 100) if total else 0
    if hard_pct >= 15:
        dsa += 1
        dsa_bits.append(f"{hard_pct:.0f}% hard")

    if rating >= 2100:
        dsa += 2
        dsa_bits.append(f"contest rating {rating}")
    elif rating >= 1800:
        dsa += 1
        dsa_bits.append(f"contest rating {rating}")

    dsa = min(dsa, 10)

    # COD — volume implies fluency, capped lower than DSA.
    cod = min(8, 3 + total // 100)
    cod_reason = f"{total} problems solved"

    # APTI — problem-solving under contest constraints.
    if rating >= 2200:
        apti, apti_reason = 8, f"contest rating {rating}"
    elif rating >= 1900:
        apti, apti_reason = 7, f"contest rating {rating}"
    elif rating >= 1600:
        apti, apti_reason = 6, f"contest rating {rating}"
    else:
        apti = min(7, dsa - 1)
        apti_reason = "no contest rating — derived from DSA level"

    return {
        "DSA": {"level": dsa, "reason": ", ".join(dsa_bits)},
        "COD": {"level": cod, "reason": cod_reason},
        "APTI": {"level": max(apti, 0), "reason": apti_reason},
    }


def hackerrank_to_levels(stats: dict) -> dict[str, dict]:
    """Star ratings per track -> levels. Treated as a floor, not an override —
    HackerRank stars are easier to earn than LeetCode volume, so results here
    still go through the same "verified only raises" merge rule as LeetCode."""
    ps_stars = stats.get("problem_solving_stars") or 0
    lang_stars = stats.get("language_stars") or 0
    gold_badges = stats.get("gold_badges") or 0

    levels: dict[str, dict] = {}

    if ps_stars:
        dsa = round(ps_stars / 5 * 7)
        bits = [f"{ps_stars}-star Problem Solving"]
        if gold_badges:
            dsa += 1
            bits.append(f"{gold_badges} gold badge(s)")
        levels["DSA"] = {"level": min(dsa, 10), "reason": ", ".join(bits)}

    if lang_stars:
        cod = round(lang_stars / 5 * 7)
        bits = [f"{lang_stars}-star language track"]
        if gold_badges:
            cod += 1
            bits.append(f"{gold_badges} gold badge(s)")
        levels["COD"] = {"level": min(cod, 10), "reason": ", ".join(bits)}

    return levels


# ---------------------------------------------------------------------------
# F1.6 — merge rule: verified data raises a level, it never lowers one.
# ---------------------------------------------------------------------------

def merge_verified_levels(estimated_levels: dict[str, int], verified: dict[str, dict]) -> dict[str, dict]:
    """`verified` is {code: {"level", "reason", "platform"}} for the subset of
    codes (DSA/COD/APTI) that have coding-profile evidence. Returns, for every
    code in `estimated_levels`, the merged detail record used by Talent Check."""
    result: dict[str, dict] = {}
    for code, estimated_level in estimated_levels.items():
        v = verified.get(code)
        if v is None:
            result[code] = {
                "level": estimated_level, "estimated_level": estimated_level,
                "verified_level": None, "source": "estimated", "evidence": "",
            }
            continue

        verified_level = v["level"]
        if verified_level > estimated_level:
            result[code] = {
                "level": verified_level, "estimated_level": estimated_level,
                "verified_level": verified_level, "source": "verified",
                "evidence": f"verified: {v['reason']} ({v['platform']})",
            }
        else:
            result[code] = {
                "level": estimated_level, "estimated_level": estimated_level,
                "verified_level": verified_level, "source": "estimated",
                "evidence": f"estimated (coding profile suggested {verified_level})",
            }
    return result


def verified_levels_from_coding_profiles(coding_profiles: dict | None) -> dict[str, dict]:
    """Combine LeetCode + HackerRank (whichever are present) into a single
    per-category verified-level record, taking the higher of the two when both
    cover the same category. Only DSA/COD/APTI are ever touched (F1.2)."""
    if not coding_profiles:
        return {}

    candidates: dict[str, list[dict]] = {"DSA": [], "COD": [], "APTI": []}

    leetcode = coding_profiles.get("leetcode")
    if leetcode and leetcode.get("total_solved") is not None:
        for code, info in leetcode_to_levels(leetcode).items():
            candidates[code].append({**info, "platform": "LeetCode"})

    hackerrank = coding_profiles.get("hackerrank")
    if hackerrank and (hackerrank.get("problem_solving_stars") or hackerrank.get("language_stars")):
        for code, info in hackerrank_to_levels(hackerrank).items():
            candidates[code].append({**info, "platform": "HackerRank"})

    return {
        code: max(options, key=lambda o: o["level"])
        for code, options in candidates.items() if options
    }


# ---------------------------------------------------------------------------
# F1.4 — fetching, cache-first, never blocks the app.
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def fetch_leetcode(username: str, use_cache: bool = True, timeout: float = FETCH_TIMEOUT_SECONDS) -> dict:
    """Returns {"stats": dict|None, "source": "cached"|"fetched"|None, "error": str|None}.
    Never raises — any failure (network, parse, missing profile) becomes `error`."""
    username = (username or "").strip()
    if not username:
        return {"stats": None, "source": None, "error": None}

    if use_cache:
        cached = load_coding_cache("leetcode", username)
        if cached is not None:
            return {"stats": cached, "source": "cached", "error": None}

    try:
        import requests

        query = """
        query getUserStats($username: String!) {
          matchedUser(username: $username) {
            username
            submitStatsGlobal { acSubmissionNum { difficulty count } }
          }
          userContestRanking(username: $username) { rating }
        }
        """
        response = requests.post(
            "https://leetcode.com/graphql",
            json={"query": query, "variables": {"username": username}},
            timeout=timeout,
            headers={"Content-Type": "application/json", "Referer": f"https://leetcode.com/{username}/"},
        )
        response.raise_for_status()
        body = response.json().get("data") or {}
        matched = body.get("matchedUser")
        if matched is None:
            return {"stats": None, "source": None,
                     "error": f"Couldn't find a LeetCode profile for \"{username}\". Enter your numbers manually below."}

        counts = {row["difficulty"]: row["count"] for row in matched["submitStatsGlobal"]["acSubmissionNum"]}
        contest = body.get("userContestRanking") or {}
        stats = {
            "username": username,
            "url": f"https://leetcode.com/u/{username}",
            "total_solved": counts.get("All", 0),
            "easy": counts.get("Easy", 0),
            "medium": counts.get("Medium", 0),
            "hard": counts.get("Hard", 0),
            "contest_rating": round(contest["rating"]) if contest.get("rating") else None,
            "fetched_at": _now_iso(),
            "source": "fetched",
        }
        save_coding_cache("leetcode", username, stats)
        return {"stats": stats, "source": "fetched", "error": None}
    except Exception:
        return {"stats": None, "source": None,
                 "error": "Couldn't reach LeetCode. Enter your numbers manually below."}


def fetch_hackerrank(username: str, use_cache: bool = True, timeout: float = FETCH_TIMEOUT_SECONDS) -> dict:
    """Bonus path (F1.4/F1.5) — HackerRank has no stable public API, so this is
    best-effort only. Manual entry is the primary path for this platform."""
    username = (username or "").strip()
    if not username:
        return {"stats": None, "source": None, "error": None}

    if use_cache:
        cached = load_coding_cache("hackerrank", username)
        if cached is not None:
            return {"stats": cached, "source": "cached", "error": None}

    try:
        import requests

        response = requests.get(
            f"https://www.hackerrank.com/rest/hackers/{username}/badges", timeout=timeout
        )
        response.raise_for_status()
        badges = (response.json() or {}).get("models", [])
        if not badges:
            return {"stats": None, "source": None,
                     "error": f"Couldn't find HackerRank badges for \"{username}\". Enter your numbers manually below."}

        ps_stars, lang_stars, gold_badges = 0, 0, 0
        language_tracks = {"python", "java", "c++", "c", "javascript", "ruby", "go", "kotlin", "scala", "swift"}
        for badge in badges:
            stars = badge.get("stars") or 0
            name = (badge.get("badge_name") or "").lower()
            if "problem solving" in name:
                ps_stars = max(ps_stars, stars)
            elif name in language_tracks:
                lang_stars = max(lang_stars, stars)
            if stars >= 5:
                gold_badges += 1

        stats = {
            "username": username,
            "url": f"https://www.hackerrank.com/{username}",
            "problem_solving_stars": ps_stars,
            "language_stars": lang_stars,
            "gold_badges": gold_badges,
            "fetched_at": _now_iso(),
            "source": "fetched",
        }
        save_coding_cache("hackerrank", username, stats)
        return {"stats": stats, "source": "fetched", "error": None}
    except Exception:
        return {"stats": None, "source": None,
                 "error": "Couldn't reach HackerRank. Enter your numbers manually below."}


def manual_leetcode_stats(username: str, total_solved: int, easy: int, medium: int,
                           hard: int, contest_rating: int | None) -> dict:
    return {
        "username": username or "(manual entry)",
        "url": f"https://leetcode.com/u/{username}" if username else "",
        "total_solved": total_solved, "easy": easy, "medium": medium, "hard": hard,
        "contest_rating": contest_rating or None,
        "fetched_at": _now_iso(), "source": "manual",
    }


def manual_hackerrank_stats(username: str, problem_solving_stars: int,
                             language_stars: int, gold_badges: int) -> dict:
    return {
        "username": username or "(manual entry)",
        "url": f"https://www.hackerrank.com/{username}" if username else "",
        "problem_solving_stars": problem_solving_stars, "language_stars": language_stars,
        "gold_badges": gold_badges, "fetched_at": _now_iso(), "source": "manual",
    }
